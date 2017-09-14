# coding: utf-8
"""DDB File."""
from __future__ import print_function, division, unicode_literals, absolute_import

import sys
import os
import tempfile
import numpy as np
from collections import OrderedDict

from six.moves import map, zip, StringIO
from monty.string import marquee
from monty.collections import AttrDict, dict2namedtuple, tree
from monty.functools import lazy_property
from monty.termcolor import cprint
from monty.dev import get_ncpus, deprecated
from abipy.flowtk import NetcdfReader, AnaddbTask
from abipy.core.mixins import TextFile, Has_Structure, NotebookWriter
from abipy.core.symmetries import AbinitSpaceGroup
from abipy.core.structure import Structure
from abipy.core.kpoints import KpointList
from abipy.core.tensor import Tensor
from abipy.iotools import ETSF_Reader
from abipy.abio.inputs import AnaddbInput
from abipy.dfpt.phonons import PhononDosPlotter, InteratomicForceConstants
from abipy.dfpt.tensors import DielectricTensor
from abipy.core.abinit_units import Ha_cmm1
from pymatgen.analysis.elasticity.elastic import ElasticTensor
from pymatgen.core.units import eV_to_Ha, bohr_to_angstrom
from abipy.tools.plotting import Marker, add_fig_kwargs, get_ax_fig_plt, set_axlims
from abipy.tools import duck


import logging
logger = logging.getLogger(__name__)


class DdbError(Exception):
    """Error class raised by DDB."""


class AnaddbError(DdbError):
    """
    Exceptions raised when we try to execute :class:`AnaddbTask` in the :class:`DdbFile` methods

    An `AnaddbError` has a reference to the task and to the :class:`EventsReport` that contains
    the error messages of the run.
    """
    def __init__(self, *args, **kwargs):
        self.task, self.report = kwargs.pop("task"), kwargs.pop("report")
        super(AnaddbError, self).__init__(*args, **kwargs)

    def __str__(self):
        lines = ["\nworkdir = %s" % self.task.workdir]
        app = lines.append

        if self.report.errors:
            app("Found %d errors" % len(self.report.errors))
            lines += [str(err) for err in self.report.errors]

        return "\n".join(lines)


class DdbFile(TextFile, Has_Structure, NotebookWriter):
    """
    This object provides an interface to the DDB file produced by ABINIT
    as well as methods to compute phonon band structures, phonon DOS, thermodinamical properties ...
    """
    Error = DdbError
    AnaddbError = AnaddbError

    @classmethod
    def from_file(cls, filepath):
        """Needed for the `AbinitFile` abstract interface."""
        return cls(filepath)

    def __init__(self, filepath):
        super(DdbFile, self).__init__(filepath)

        self._header = self._parse_header()

        self._structure = Structure.from_abivars(**self.header)
        # Add AbinitSpacegroup (needed in guessed_ngkpt)
        # FIXME: kptopt is not reported in the header --> has_timerev is always set to True
        spgid, has_timerev, h = 0, True, self.header
        self._structure.set_abi_spacegroup(AbinitSpaceGroup(spgid, h.symrel, h.tnons, h.symafm, has_timerev))

        frac_coords = self._read_qpoints()
        self._qpoints = KpointList(self.structure.lattice.reciprocal_lattice, frac_coords, weights=None, names=None)

    def __str__(self):
        """String representation."""
        return self.to_string()

    def to_string(self, verbose=0):
        """String representation."""
        lines = []
        app, extend = lines.append, lines.extend

        app(marquee("File Info", mark="="))
        app(self.filestat(as_string=True))
        app("")
        app(marquee("Structure", mark="="))
        app(str(self.structure.to_string(verbose=verbose)))

        app(marquee("Q-points", mark="="))
        app(str(self.qpoints))
        app("guessed_ngqpt: %s" % self.guessed_ngqpt)

        return "\n".join(lines)

    @property
    def structure(self):
        """Abipy Structure."""
        return self._structure

    @property
    def natom(self):
        """Number of atoms in structure"""
        return len(self.structure)

    @property
    def version(self):
        """DDB Version number (integer)."""
        return self.header["version"]

    @property
    def header(self):
        """
        Dictionary with the values reported in the header section.
        Use ddb.header.ecut to access its values
        """
        return self._header

    def _parse_header(self):
        """Parse the header sections. Returns :class:`AttrDict` dictionary."""
        #ixc         7
        #kpt  0.00000000000000D+00  0.00000000000000D+00  0.00000000000000D+00
        #     0.25000000000000D+00  0.00000000000000D+00  0.00000000000000D+00
        self.seek(0)
        keyvals = []
        header_lines = []
        for i, line in enumerate(self):
            header_lines.append(line.rstrip())
            line = line.strip()
            if not line: continue
            if "Version" in line:
                # +DDB, Version number    100401
                version = int(line.split()[-1])

            if line in ("Description of the potentials (KB energies)",
                        "No information on the potentials yet",
                        "Description of the PAW dataset(s)"):
                # Skip section with psps info.
                break

            # header starts here
            if i >= 6:
                # Python does not support exp format with D
                line = line.replace("D+", "E+").replace("D-", "E-")
                tokens = line.split()
                key = None
                try:
                    float(tokens[0])
                    parse = float if "." in tokens[0] else int
                    keyvals[-1][1].extend(list(map(parse, tokens)))
                except ValueError:
                    # We have a new key
                    key = tokens.pop(0)
                    parse = float if "." in tokens[0] else int
                    keyvals.append((key, list(map(parse, tokens))))

        # add the potential information
        for line in self:
            if "Database of total energy derivatives" in line:
                break
            header_lines.append(line.rstrip())

        h = AttrDict(version=version, lines=header_lines)
        for key, value in keyvals:
            if len(value) == 1: value = value[0]
            h[key] = value

        # Convert to array. Note that znucl is converted into integer
        # to avoid problems with pymatgen routines that expect integral Z
        # This of course will break any code for alchemical mixing.
        arrays = {
            "kpt": dict(shape=(h.nkpt, 3), dtype=np.double),
            "rprim": dict(shape=(3, 3), dtype=np.double),
            "symrel": dict(shape=(h.nsym, 3, 3), dtype=np.int),
            "tnons": dict(shape=(h.nsym, 3), dtype=np.double),
            "xred":  dict(shape=(h.natom, 3), dtype=np.double),
            "znucl": dict(shape=(-1,), dtype=np.int),
            "symafm": dict(shape=(-1,), dtype=np.int),
        }

        for k, ainfo in arrays.items():
            h[k] = np.reshape(np.array(h[k], dtype=ainfo["dtype"]), ainfo["shape"])

        # Transpose symrel because Abinit write matrices by colums.
        h.symrel = np.array([s.T for s in h.symrel])

        return h

    def _read_qpoints(self):
        """Read the list q-points from the DDB file. Returns `ndarray`"""
        # 2nd derivatives (non-stat.)  - # elements :      36
        # qpt  2.50000000E-01  0.00000000E+00  0.00000000E+00   1.0

        # Since there are multiple occurrences of qpt in the DDB file
        # we use seen to remove duplicates.
        self.seek(0)
        tokens, seen = [], set()

        for line in self:
            line = line.strip()
            if line.startswith("qpt") and line not in seen:
                seen.add(line)
                tokens.append(line.replace("qpt", ""))

        qpoints, weights = [], []
        for tok in tokens:
            nums = list(map(float, tok.split()))
            qpoints.append(nums[:3])
            weights.append(nums[3])

        return np.reshape(qpoints, (-1,3))

    @lazy_property
    def blocks(self):
        """
        DDB blocks. List of dictionaries, Each dictionary contains "qpt"
        with the reduced coordinates of the q-point and "data" that is a list of strings
        with the entries of the dynamical matrix for this q-point.
        """
        return self._read_blocks()

    def _read_blocks(self):
        self.seek(0)

        # skip until the beginning of the db
        while "Number of data blocks" not in self._file.readline():
            pass

        blocks = []

        block_lines = []
        qpt = None
        for line in self:
            # skip empty lines
            if line.isspace():
                continue

            if "List of bloks and their characteristics" in line:
                #add last block
                blocks.append({"data": block_lines, "qpt": qpt})
                break

            line = line.rstrip()
            # new block
            if "# elements" in line:
                if block_lines:
                    blocks.append({"data": block_lines, "qpt": qpt})
                block_lines = []
                qpt = None

            block_lines.append(line)
            if "qpt" in line:
                qpt = list(map(float, line.split()[1:4]))

        # TODO: Create mapping [(idir1, ipert1), (idir2, ipert2)] --> element

        return blocks

    @property
    def qpoints(self):
        """:class:`KpointList` object with the list of q-points in reduced coordinates."""
        return self._qpoints

    def qindex(self, qpoint):
        """
        The index of the q-point in the internal list of q-points.
        Accepts: :class:`Kpoint` instance or integer.
        """
        if duck.is_intlike(qpoint):
            return int(qpoint)
        else:
            return self.qpoints.index(qpoint)

    @lazy_property
    def guessed_ngqpt(self):
        """
        Guess for the q-mesh divisions (ngqpt) inferred from the list of
        q-points found in the DDB file.

        .. warning::

            The mesh may not be correct if the DDB file contains points belonging
            to different meshes and/or the Q-mesh is shifted.
        """
        return self._guess_ngqpt()

    def _guess_ngqpt(self):
        """
        This function tries to figure out the value of ngqpt from the list of
        points reported in the DDB file.
        """
        if not self.qpoints: return None
        # Build the union of the stars of the q-points.
        all_qpoints = np.empty((len(self.qpoints) * len(self.structure.abi_spacegroup), 3))
        count = 0
        for qpoint in self.qpoints:
            for op in self.structure.abi_spacegroup:
                all_qpoints[count] = op.rotate_k(qpoint.frac_coords, wrap_tows=False)
                count += 1

        # Replace zeros with np.inf
        for q in all_qpoints:
            q[q == 0] = np.inf

        # Compute the minimum of the fractional coordinates along the 3 directions and invert
        #print(all_qpoints)
        smalls = np.abs(all_qpoints).min(axis=0)
        smalls[smalls == 0] = 1
        ngqpt = np.rint(1 / smalls)
        ngqpt[ngqpt == 0] = 1

        return np.array(ngqpt, dtype=np.int)

    @property
    def params(self):
        """Dictionary with the parameters that are usually tested for convergence."""
        return {k: v for k, v in self.header.items() if k in ("nkpt", "nsppol", "ecut", "tsmear", "ixc")}

    # TODO
    # API to understand if the DDB contains the info we are looking for.
    # NB: This requires the parsing of the dynamical matrix
    #def has_phonon_terms(self, qpoint)
    #    """True if the DDB file contains info on the phonon perturbation."""

    #def has_emacro_terms(self, ij="at_least_one"):
    #    """
    #    True if the DDB file contains info on the electric-field perturbation.

    #        Args:
    #            ij: Possible values in ["at_least_one", "all"] or tuple e.g. (0, 1)
    #            If ij == "at_least_one", we check if there's at least one entry associated to the electric field.
    #            and we assume that anaddb will be able to reconstruct the full tensor by symmetry.
    #            If ij == "all", all tensor components must be present in the DDB file.
    #            If ij == (0, 1), the method returns False if the (0, 1) component of the tensor is not present in the DDB.
    #    """

    #def has_bec_terms(self, ij="at_least_one"):
    #    """
    #    True if the DDB file contains info on the Born effective charges.
    #    By default, we check if there's at least one entry associated to electric field.
    #    and we assume that anaddb will be able to reconstruct the full tensor by symmetry

    #    Args:
    #            ij: "at_least_one", "all", (1,2)
    #    """

    #def has_lo_to_data(self)
    #    """True if the DDB file contains data requires to compute LO-TO splitting."""
    #    return self.has_bec_terms() and self.has_emacro_terms()

    def anaget_phmodes_at_qpoint(self, qpoint=None, asr=2, chneut=1, dipdip=1, workdir=None, mpi_procs=1,
                                 manager=None, verbose=0, lo_to_splitting=False, directions=None, anaddb_kwargs=None):
        """
        Execute anaddb to compute phonon modes at the given q-point.

        Args:
            qpoint: Reduced coordinates of the qpoint where phonon modes are computed.
            asr, chneut, dipdp: Anaddb input variable. See official documentation.
            workdir: Working directory. If None, a temporary directory is created.
            mpi_procs: Number of MPI processes to use.
            manager: :class:`TaskManager` object. If None, the object is initialized from the configuration file
            verbose: verbosity level. Set it to a value > 0 to get more information
            lo_to_splitting: if True the LO-TO splitting will be calculated if qpoint==Gamma and the non_anal_directions
                non_anal_phfreqs attributes will be added to the returned object
            directions: list of 3D directions along which the LO-TO splitting will be calculated. If None the three
                cartesian direction will be used
            anaddb_kwargs: additional kwargs for anaddb

        Return:
            :class:`PhononBands` object.
        """
        if qpoint is None:
            qpoint = self.qpoints[0]
            if len(self.qpoints) != 1:
                raise ValueError("%s contains %s qpoints and the choice is ambiguous.\n"
                                 "Please specify the qpoint." % (self, len(self.qpoints)))

        # Check if qpoint is in the DDB.
        try:
            self.qindex(qpoint)
        except:
            raise ValueError("input qpoint %s not in ddb.qpoints:%s\n" % (qpoint, self.qpoints))

        #if lo_to_splitting and not self.has_lo_to_data:
        #    cprint("lo_to_splitting set to True but Emacro and Becs are not available in DDB:" % self.filepath

        inp = AnaddbInput.modes_at_qpoint(self.structure, qpoint, asr=asr, chneut=chneut, dipdip=dipdip,
                                          lo_to_splitting=lo_to_splitting, directions=directions,
                                          anaddb_kwargs=anaddb_kwargs)

        task = AnaddbTask.temp_shell_task(inp, ddb_node=self.filepath, workdir=workdir, manager=manager, mpi_procs=mpi_procs)

        if verbose:
            print("ANADDB INPUT:\n", inp)
            print("workdir:", task.workdir)

        # Run the task here
        task.start_and_wait(autoparal=False)
        report = task.get_event_report()
        if not report.run_completed:
            raise self.AnaddbError(task=task, report=report)

        with task.open_phbst() as ncfile:
            if lo_to_splitting and np.allclose(qpoint, [0, 0, 0]):
                ncfile.phbands.read_non_anal_from_file(os.path.join(task.workdir, "anaddb.nc"))

            return ncfile.phbands

    #def anaget_phbst_file(self, ngqpt=None, ndivsm=20, asr=2, chneut=1, dipdip=1,
    #                      workdir=None, manager=None, verbose=0, **kwargs):

    #def anaget_phdos_file(self, ngqpt=None, nqsmall=10, asr=2, chneut=1, dipdip=1, dos_method="tetra"
    #                      workdir=None, manager=None, verbose=0, **kwargs):

    def anaget_phbst_and_phdos_files(self, nqsmall=10, ndivsm=20, asr=2, chneut=1, dipdip=1, dos_method="tetra",
                                     lo_to_splitting=False, ngqpt=None, qptbounds=None, anaddb_kwargs=None, verbose=0,
                                     mpi_procs=1, workdir=None, manager=None):
        """
        Execute anaddb to compute the phonon band structure and the phonon DOS

        Args:
            nqsmall: Defines the homogeneous q-mesh used for the DOS. Gives the number of divisions
                used to sample the smallest lattice vector.
            ndivsm: Number of division used for the smallest segment of the q-path
            asr, chneut, dipdip: Anaddb input variable. See official documentation.
            dos_method: Technique for DOS computation in  Possible choices: "tetra", "gaussian" or "gaussian:0.001 eV".
                In the later case, the value 0.001 eV is used as gaussian broadening
            lo_to_splitting: if True the LO-TO splitting will be calculated and included in the band structure
            ngqpt: Number of divisions for the q-mesh in the DDB file. Auto-detected if None (default)
            qptbounds: Boundaries of the path. If None, the path is generated from an internal database
                depending on the input structure.
            anaddb_kwargs: additional kwargs for anaddb
            verbose: verbosity level. Set it to a value > 0 to get more information
            mpi_procs: Number of MPI processes to use.
            workdir: Working directory. If None, a temporary directory is created.
            manager: :class:`TaskManager` object. If None, the object is initialized from the configuration file

        Returns:
            :class:`PhbstFile` with the phonon band structure.
            :class:`PhdosFile` with the the phonon DOS.
        """
        if ngqpt is None: ngqpt = self.guessed_ngqpt

        #if lo_to_splitting and not self.has_lo_to_data:
        #    cprint("lo_to_splitting set to True but Emacro and Becs are not available in DDB:" % self.filepath

        inp = AnaddbInput.phbands_and_dos(
            self.structure, ngqpt=ngqpt, ndivsm=ndivsm, nqsmall=nqsmall, q1shft=(0, 0, 0), qptbounds=qptbounds,
            asr=asr, chneut=chneut, dipdip=dipdip, dos_method=dos_method, lo_to_splitting=lo_to_splitting,
            anaddb_kwargs=anaddb_kwargs)

        task = AnaddbTask.temp_shell_task(inp, ddb_node=self.filepath, workdir=workdir, manager=manager, mpi_procs=mpi_procs)

        if verbose:
            print("ANADDB INPUT:\n", inp)
            print("workdir:", task.workdir)

        # Run the task here.
        task.start_and_wait(autoparal=False)

        report = task.get_event_report()
        if not report.run_completed:
            raise self.AnaddbError(task=task, report=report)

        phbst = task.open_phbst()
        if lo_to_splitting:
            phbst.phbands.read_non_anal_from_file(os.path.join(task.workdir, "anaddb.nc"))

        return phbst, task.open_phdos()

    def anacompare_phdos(self, nqsmalls, asr=2, chneut=1, dipdip=1, dos_method="tetra", ngqpt=None,
                         num_cpus=1, stream=sys.stdout):
        """
        Invoke Anaddb to compute Phonon DOS with different q-meshes. The ab-initio dynamical matrix
        reported in the DDB file will be Fourier-interpolated on the list of qmeshes specified
        by `nqsmalls. Useful to perform covergence studies.

        Args:
            nqsmalls: List of integers defining the q-mesh for the DOS. Each integer gives
            the number of divisions to be used to sample the smallest reciprocal lattice vector.
            asr, chneut, dipdp: Anaddb input variable. See official documentation.
            dos_method: Technique for DOS computation in  Possible choices: "tetra", "gaussian" or "gaussian:0.001 eV".
                In the later case, the value 0.001 eV is used as gaussian broadening
            ngqpt: Number of divisions for the ab-initio q-mesh in the DDB file. Auto-detected if None (default)
            num_cpus: Number of CPUs (threads) used to parallellize the calculation of the DOSes. Autodetected if None.
            stream: File-like object used for printing.

        Return:
            `namedtuple` with the following attributes:

                phdoses: List of :class:`PhononDos` objects
                plotter: :class:`PhononDosPlotter` object. Client code can use `plotter.gridplot()`
                    to visualize the results.
        """
        num_cpus = get_ncpus() // 2 if num_cpus is None else num_cpus
        if num_cpus <= 0: num_cpus = 1
        num_cpus = min(num_cpus, len(nqsmalls))

        # TODO: anaget_phdos
        def do_work(nqsmall):
            _, phdos_file = self.anaget_phbst_and_phdos_files(
                nqsmall=nqsmall, ndivsm=1, asr=asr, chneut=chneut, dipdip=dipdip, dos_method=dos_method, ngqpt=ngqpt)
            return phdos_file.phdos

        if num_cpus == 1:
            # Sequential version
            phdoses = [do_work(nqs) for nqs in nqsmalls]

        else:
            # Threads
            print("Computing %d phonon DOS with %d threads" % (len(nqsmalls), num_cpus) )
            phdoses = [None] * len(nqsmalls)

            def worker():
                while True:
                    nqsm, phdos_index = q.get()
                    phdos = do_work(nqsm)
                    phdoses[phdos_index] = phdos
                    q.task_done()

            from threading import Thread
            try:
                from Queue import Queue # py2k
            except ImportError:
                from queue import Queue # py3k

            q = Queue()
            for i in range(num_cpus):
                 t = Thread(target=worker)
                 t.daemon = True
                 t.start()

            for i, nqsmall in enumerate(nqsmalls):
                q.put((nqsmall, i))

            # block until all tasks are done
            q.join()

        # Compute relative difference wrt last phonon DOS. Be careful because the DOSes may be defined
        # on different frequency meshes ==> spline on the mesh of the last DOS.
        last_mesh, converged = phdoses[-1].mesh, False
        for i, phdos in enumerate(phdoses[:-1]):
            splined_dos = phdos.spline_on_mesh(last_mesh)
            abs_diff = (splined_dos - phdoses[-1]).abs()
            print(" Delta(Phdos[%d] - Phdos[%d]) / Phdos[%d]: %f" %
                (i, len(phdoses)-1, len(phdoses)-1, abs_diff.integral().values[-1]), file=stream)

        # Fill the plotter.
        plotter = PhononDosPlotter()
        for nqsmall, phdos in zip(nqsmalls, phdoses):
            plotter.add_phdos(label="nqsmall %d" % nqsmall, phdos=phdos)

        return dict2namedtuple(phdoses=phdoses, plotter=plotter)

    def anaget_emacro_and_becs(self, chneut=1, mpi_procs=1, workdir=None, manager=None, verbose=0):
        """
        Call anaddb to compute the macroscopic dielectric tensor and the Born effective charges.

        Args:
            chneut: Anaddb input variable. See official documentation.
            manager: :class:`TaskManager` object. If None, the object is initialized from the configuration file
            mpi_procs: Number of MPI processes to use.
            verbose: verbosity level. Set it to a value > 0 to get more information

        Return:
            emacro, becs
        """
        inp = AnaddbInput(self.structure, anaddb_kwargs={"chneut": chneut})
        task = AnaddbTask.temp_shell_task(inp, ddb_node=self.filepath, mpi_procs=mpi_procs, workdir=workdir, manager=manager)

        if verbose:
            print("ANADDB INPUT:\n", inp)
            print("workdir:", task.workdir)

        # Run the task here.
        task.start_and_wait(autoparal=False)

        report = task.get_event_report()
        if not report.run_completed:
            raise self.AnaddbError(task=task, report=report)

        # Read data from the netcdf output file produced by anaddb.
        with ETSF_Reader(os.path.join(task.workdir, "anaddb.nc")) as r:
            structure = r.read_structure()

            emacro = Tensor.from_cartesian_tensor(r.read_value("emacro_cart"), structure.lattice, space="r"),
            becs = Becs(r.read_value("becs_cart"), structure, chneut=inp["chneut"], order="f")

            return emacro, becs

    def anaget_ifc(self, ifcout=None, asr=2, chneut=1, dipdip=1, ngqpt=None,
                   mpi_procs=1, workdir=None, manager=None, verbose=0, anaddb_kwargs=None):
        """
        Execute anaddb to compute the interatomic forces.

        Args:
            ifcout: Number of neighbouring atoms for which the ifc's will be output. If None all the atoms in the big box.
            asr, chneut, dipdip: Anaddb input variable. See official documentation.
            ngqpt: Number of divisions for the q-mesh in the DDB file. Auto-detected if None (default)
            mpi_procs: Number of MPI processes to use.
            workdir: Working directory. If None, a temporary directory is created.
            manager: :class:`TaskManager` object. If None, the object is initialized from the configuration file
            verbose: verbosity level. Set it to a value > 0 to get more information
            anaddb_kwargs: additional kwargs for anaddb

        Returns:
            :class:`InteratomicForceConstants` with the calculated ifc.
        """
        if ngqpt is None: ngqpt = self.guessed_ngqpt

        inp = AnaddbInput.ifc(self.structure, ngqpt=ngqpt, ifcout=ifcout, q1shft=(0, 0, 0), asr=asr, chneut=chneut,
                              dipdip=dipdip, anaddb_kwargs=anaddb_kwargs)

        task = AnaddbTask.temp_shell_task(inp, ddb_node=self.filepath, mpi_procs=mpi_procs, workdir=workdir, manager=manager)

        if verbose:
            print("ANADDB INPUT:\n", inp)
            print("workdir:", task.workdir)

        # Run the task here.
        task.start_and_wait(autoparal=False)

        report = task.get_event_report()
        if not report.run_completed:
            raise self.AnaddbError(task=task, report=report)

        return InteratomicForceConstants.from_file(os.path.join(task.workdir, 'anaddb.nc'))

    def write(self, filepath):
        """
        Writes the DDB file in filepath.
        Requires the blocks data.
        Only the information stored in self.header.lines and in self.blocks will be used to produce the file
        """
        lines = list(self.header.lines)

        lines.append(" **** Database of total energy derivatives ****")
        lines.append(" Number of data blocks={0:5}".format(len(self.blocks)))
        lines.append(" ")

        for b in self.blocks:
            lines.extend(b["data"])
            lines.append(" ")

        lines.append(" List of bloks and their characteristics")
        lines.append(" ")

        for b in self.blocks:
            lines.extend(b["data"][:2])
            lines.append(" ")

        with open(filepath, "wt") as f:
            f.write("\n".join(lines))

    def get_block_for_qpoint(self, qpt):
        """
        Extracts the block data for the selected qpoint.
        Returns a list of lines containing the block information
        """
        if hasattr(qpt, "frac_coords"): qpt = qpt.frac_coords

        for b in self.blocks:
            if b['qpt'] is not None and np.allclose(b['qpt'], qpt):
                return b["data"]

    def replace_block_for_qpoint(self, qpt, data):
        """
        Change the block data for the selected qpoint. Object is modified in-place.
        Data should be a list of strings representing the whole data block.
        Note that the DDB file should be written and reopened in order to call methods that run anaddb.

        Return:
            True if qpt has been found and data has been replaced.
        """
        if hasattr(qpt, "frac_coords"): qpt = qpt.frac_coords

        for b in self.blocks:
            if b['qpt'] is not None and np.allclose(b['qpt'], qpt):
                b["data"] = data
                return True

        return False

    def write_notebook(self, nbpath=None):
        """
        Write an ipython notebook to nbpath. If nbpath is None, a temporay file in the current
        working directory is created. Return path to the notebook.
        """
        nbformat, nbv, nb = self.get_nbformat_nbv_nb(title=None)

        nb.cells.extend([
            nbv.new_code_cell("ddb = abilab.abiopen('%s')" % self.filepath),
            nbv.new_code_cell("units = 'eV'\nprint(ddb)"),
            nbv.new_code_cell("# display(ddb.header)"),
            nbv.new_markdown_cell("## Invoke `anaddb` to compute bands and dos"),
            nbv.new_code_cell("""\
bstfile, phdosfile =  ddb.anaget_phbst_and_phdos_files(nqsmall=10, ndivsm=20,
    asr=2, chneut=1, dipdip=0, lo_to_splitting=False,
    dos_method="tetra", ngqpt=None, qptbounds=None, verbose=0, anaddb_kwargs=None)

phbands, phdos = bstfile.phbands, phdosfile.phdos"""),
            nbv.new_markdown_cell("## q-point path"),
            nbv.new_code_cell("fig = phbands.qpoints.plot()"),
            nbv.new_markdown_cell("## Phonon bands with DOS"),
            nbv.new_code_cell("fig = phbands.plot_with_phdos(phdos, units=units)"),
            nbv.new_markdown_cell("## Phonon fatbands with DOS"),
            nbv.new_code_cell("fig = phbands.plot_fatbands(phdos_file=phdosfile, units=units)"),
            nbv.new_markdown_cell("## Distribution of phonon frequencies wrt mode index"),
            nbv.new_code_cell("fig = phbands.boxplot(units=units)"),
            nbv.new_markdown_cell("## Phonon band structure with different color for each line"),
            nbv.new_code_cell("fig = phbands.plot_colored_matched(units=units)"),
            nbv.new_markdown_cell("## Type-projected phonon DOS."),
            nbv.new_code_cell("fig = phdosfile.plot_pjdos_type(units=units)"),
            nbv.new_markdown_cell("## Type-projected phonon DOS decomposed along the three reduced directions"),
            nbv.new_code_cell("fig = phdosfile.plot_pjdos_redirs_type(units=units)"),
            nbv.new_code_cell("#fig = phdosfile.plot_pjdos_redirs_site(units=units)"),
            nbv.new_markdown_cell("## Thermodinamic properties within the harmonic approximation"),
            nbv.new_code_cell("fig = phdosfile.phdos.plot_harmonic_thermo(tstart=5, tstop=300)"),

            nbv.new_markdown_cell("## Macroscopic dielectric tensor and Born effective charges"),
            nbv.new_code_cell("""\
if False:
    emacro, becs = ddb.anaget_emacro_and_becs()
    print(emacro)
    print(becs)"""),

            nbv.new_markdown_cell("## Call `anaddb` to compute phonon DOS with different BZ samplings"),
            nbv.new_code_cell("""\
c = None
if False:
    c = ddb.anacompare_phdos(nqsmalls=[20, 30], asr=2, chneut=1, dipdip=1,
            dos_method="tetra", ngqpt=None, num_cpus=1)"""),

            nbv.new_code_cell("""\
if c is not None:
    c.plotter.ipw_select_plot()
    #for phdos in c.phdoses"""),

            nbv.new_markdown_cell("## Analysis of the IFCs in real-space"),
            nbv.new_code_cell("""\
ifc = None
if False:
    ifc = ddb.anaget_ifc(ifcout=None, asr=2, chneut=1, dipdip=1, ngqpt=None, verbose=0, anaddb_kwargs=None)"""),

            nbv.new_code_cell("""\
if ifc is not None:
    fig = ifc.plot_longitudinal_ifc(atom_indices=None, atom_element=None, neighbour_element=None, min_dist=None,
                                    max_dist=None, ax=None)"""),
            nbv.new_code_cell("""\
if ifc is not None:
    fig = ifc.plot_longitudinal_ifc_short_range(atom_indices=None, atom_element=None, neighbour_element=None)"""),
            nbv.new_code_cell("""\
if ifc is not None:
    fig = ifc.plot_longitudinal_ifc_ewald(atom_indices=None, atom_element=None, neighbour_element=None,
                                          min_dist=None, max_dist=None, ax=None)"""),
        ])

        return self._write_nb_nbpath(nb, nbpath)


class Becs(Has_Structure):
    """
    This object stores the Born effective charges and provides simple tools for data analysis.
    """

    def __init__(self, becs_arr, structure, chneut, order="c"):
        """
        Args:
            becs_arr: (3, 3, natom) array with the Born effective charges in Cartesian coordinates.
            structure: Structure object.
            chneut: Option used for the treatment of the Charge Neutrality requirement
                for the effective charges (anaddb input variable)
            order: "f" if becs_arr is in Fortran order.
        """
        assert len(becs_arr) == len(structure)
        self._structure = structure
        self.chneut = chneut

        self.values = np.empty((len(structure), 3, 3))
        for i, bec in enumerate(becs_arr):
            mat = becs_arr[i]
            if order.lower() == "f": mat = mat.T
            self.values[i] = mat

    @property
    @deprecated(message="becs  has been renamed values. Will be removed in abipy 0.4.")
    def becs(self):
        return self.values

    @property
    def structure(self):
        return self._structure

    def __repr__(self):
        return self.to_string()

    def to_string(self, verbose=0):
        lines = []
        app = lines.append
        app("Born effective charges computed with chneut: %d" % self.chneut)

        for site, bec in zip(self.structure, self.values):
            app("BEC at site: %s" % repr(site))
            app(str(bec))
            app("")

        # Add info on the bec sum rule.
        stream = StringIO()
        self.check_sumrule(stream=stream)
        app(stream.getvalue())

        return "\n".join(lines)

    def check_sumrule(self, stream=sys.stdout):
        stream.write("Born effective charge neutrality sum-rule with chneut: %d\n" % self.chneut)
        becs_atomsum = self.values.sum(axis=0)
        stream.write(str(becs_atomsum))


class ElasticComplianceTensor(Has_Structure):
    """This object is used to store the elastic and compliance tensors."""

    def __init__(self, elastic_tensor, compliance_tensor, structure, additional_info=None):
        """

        Args:
            elastic_tensor: (6, 6) array with the elastic tensor in Cartesian coordinates
            compliance_tensor: (6, 6) array with the compliance tensor in Cartesian coordinates
            structure: Structure object.
        """
        self._structure = structure
        self.elastic_tensor = elastic_tensor
        self.compliance_tensor = compliance_tensor
        self.additional_info = additional_info

    @property
    def structure(self):
        return self._structure

    def __repr__(self):
        return self.to_string()

    @classmethod
    def from_ec_nc_file(cls, ec_nc_file, tensor_type='relaxed_ion'):
        with NetcdfReader(ec_nc_file) as nc_reader:
            if tensor_type == 'relaxed_ion':
                ec = np.array(nc_reader.read_variable('elastic_constants_relaxed_ion'))
                compl = np.array(nc_reader.read_variable('compliance_constants_relaxed_ion'))
            elif tensor_type == 'clamped_ion':
                ec = np.array(nc_reader.read_variable('elastic_constants_clamped_ion'))
                compl = np.array(nc_reader.read_variable('compliance_constants_clamped_ion'))
            elif tensor_type == 'relaxed_ion_stress_corrected':
                ec = np.array(nc_reader.read_variable('elastic_constants_relaxed_ion_stress_corrected'))
                compl = np.array(nc_reader.read_variable('compliance_constants_relaxed_ion_stress_corrected'))
            else:
                raise ValueError('tensor_type "{0}" not allowed'.format(tensor_type))
        #TODO: add the structure object!
        return cls(elastic_tensor=ec, compliance_tensor=compl, structure=None,
                   additional_info={'tensor_type': tensor_type})

    def as_dict(self):
        return {'elastic_tensor': self.elastic_tensor, 'compliance_tensor': self.compliance_tensor,
                'structure': self.structure.as_dict() if self.structure is not None else None,
                'additional_info': self.additional_info}

    def extended_dict(self):
        dd = self.as_dict()
        K_Voigt = (self.elastic_tensor[0, 0] + self.elastic_tensor[1, 1] + self.elastic_tensor[2, 2] +
                   2.0*self.elastic_tensor[0, 1] + 2.0*self.elastic_tensor[1, 2] + 2.0*self.elastic_tensor[2, 0]) / 9.0
        K_Reuss = 1.0 / (self.compliance_tensor[0, 0] + self.compliance_tensor[1, 1] + self.compliance_tensor[2, 2] +
                         2.0*self.compliance_tensor[0, 1] + 2.0*self.compliance_tensor[1, 2] +
                         2.0*self.compliance_tensor[2, 0])
        G_Voigt = (self.elastic_tensor[0, 0] + self.elastic_tensor[1, 1] + self.elastic_tensor[2, 2] -
                   self.elastic_tensor[0, 1] - self.elastic_tensor[1, 2] - self.elastic_tensor[2, 0] +
                   3.0*self.elastic_tensor[3, 3] + 3.0*self.elastic_tensor[4, 4] + 3.0*self.elastic_tensor[5, 5]) / 15.0
        G_Reuss = 15.0 / (4.0*self.compliance_tensor[0, 0] + 4.0*self.compliance_tensor[1, 1] +
                          4.0*self.compliance_tensor[2, 2] - 4.0*self.compliance_tensor[0, 1] -
                          4.0*self.compliance_tensor[1, 2] - 4.0*self.compliance_tensor[2, 0] +
                          3.0*self.compliance_tensor[3, 3] + 3.0*self.compliance_tensor[4, 4] +
                          3.0*self.compliance_tensor[5, 5])
        K_VRH = (K_Voigt + K_Reuss) / 2.0
        G_VRH = (G_Voigt + G_Reuss) / 2.0
        universal_elastic_anisotropy = 5.0*G_Voigt/G_Reuss + K_Voigt/K_Reuss - 6.0
        isotropic_poisson_ratio = (3.0*K_VRH - 2.0*G_VRH) / (6.0*K_VRH + 2.0*G_VRH)
        dd['K_Voigt'] = K_Voigt
        dd['G_Voigt'] = G_Voigt
        dd['K_Reuss'] = K_Reuss
        dd['G_Reuss'] = G_Reuss
        dd['K_VRH'] = K_VRH
        dd['G_VRH'] = G_VRH
        dd['universal_elastic_anistropy'] = universal_elastic_anisotropy
        dd['isotropic_poisson_ratio'] = isotropic_poisson_ratio
        return dd

    @classmethod
    def from_dict(cls, dd):
        return cls(elastic_tensor=dd['elastic_tensor'], compliance_tensor=dd['compliance_tensor'],
                   structure=dd['structure'] if dd['structure'] is not None else None,
                   additional_info=dd['additional_info'])

    def get_pmg_elastic_tensor(self):
        """
        Converts to a pymatgen ElasticTensor object.
        """
        return ElasticTensor.from_voigt(self.elastic_tensor)


class DielectricTensorGenerator(Has_Structure):
    """
    Object used to generate frequency dependent dielectric tensors as obtained
    from DFPT calculations. The values are calculated on the fly
    based on the phonon frequencies at gamma and oscillator strengths.
    The first three frequencies would be considered as acoustic modes and
    ignored in the calculation. No checks would be performed.
    """

    def __init__(self, phfreqs, oscillator_strength, emacro, structure):
        """
        Args:
             phfreqs: a numpy array containing the 3*(num atoms) phonon frequencies at gamma
             oscillator_strength: a complex numpy array with shape (number of phonon modes, 3, 3) in atomic units
             emacro: a numpy array containing the dielectric tensor without frequency dependence
                (at infinite frequency)
             structure: a pymatgen Structure of the system considered
        """
        self.phfreqs = phfreqs
        self.oscillator_strength = oscillator_strength
        self.emacro = emacro
        self._structure = structure

    @property
    def structure(self):
        return self._structure

    @classmethod
    def from_files(cls, phbst_filepath, anaddbnc_filepath):
        """
        Generates the object from the files that contain the phonon frequencies, oscillator strength and
        static dielectric tensor, i.e. the PHBST and anaddb netcdf files, respectively.
        """

        with ETSF_Reader(phbst_filepath) as reader_phbst:
            qpts = reader_phbst.read_value("qpoints")
            full_phfreqs = reader_phbst.read_value("phfreqs")

        for i, q in enumerate(qpts):
            if np.array_equal(q, [0, 0, 0]):
                break
        else:
            raise ValueError('The PHBST does not containg the frequencies at gamma')

        phfreqs = full_phfreqs[i]

        with ETSF_Reader(anaddbnc_filepath) as reader_anaddbnc:
            emacro = reader_anaddbnc.read_value("emacro_cart")

            try:
                oscillator_strength = reader_anaddbnc.read_value("oscillator_strength", cmode="c")
            except Exception as exc:
                import traceback
                msg = traceback.format_exc()
                msg += ("Error while trying to read from file.\n"
                        "Verify that dieflag == 1, 3 or 4 in anaddb\n")
                raise ValueError(msg)

            structure = reader_anaddbnc.read_structure()

        return cls(phfreqs, oscillator_strength, emacro, structure)

    @classmethod
    def from_objects(cls, phbands, anaddbnc):
        """
        Generates the object from the objects PhononBands and AnaddbNcFile
        """
        gamma_index = phbands.qindex([0, 0, 0])

        phfreqs = phbands.phfreqs[gamma_index]

        emacro = anaddbnc.emacro.cartesian_tensor
        oscillator_strength = anaddbnc.oscillator_strength

        return cls(phfreqs, oscillator_strength, emacro, anaddbnc.structure)

    def tensor_at_frequency(self, w, units='eV'):
        """
        Returns a DielectricTensor object representing
        the dielectric tensor in atomic units at the specified frequency w.
        Args:
            w: frequency
            units: string specifying the units used for the frequency. Accepted values are Ha, eV (default), cm-1
        """

        if units == 'eV':
            pass
        elif units == 'Ha':
            w = w / eV_to_Ha
        elif units == 'cm-1':
            w = w / Ha_cmm1 / eV_to_Ha
        else:
            raise ValueError('Unknown units {}'.format(units))

        t = np.zeros((3,3))
        for i in range(3, len(self.phfreqs)):
            t += self.oscillator_strength[i].real/(self.phfreqs[i]**2 - w**2)

        vol = self.structure.volume / bohr_to_angstrom ** 3
        t = 4*np.pi*t/vol/eV_to_Ha**2

        t += self.emacro

        return DielectricTensor(t)

    @add_fig_kwargs
    def plot_vs_w(self, w_min, w_max, num, component='diago', units='eV', ax=None, **kwargs):
        """
        Plots the selected components of the dielectric tensor as a function of the frequency

        Args:
            w_min: minimum frequency
            w_max: maximum frequqncy
            num: number of values of the frequencies between w_min and w_max
            component: determine which components of the tensor will be displayed. Can be a list/tuple of two
                elements, indicating the indices [i, j] of the desired component or a string among
                'diag': plots the elements on diagonal
                'all': plots all the components
                'diag_av': plots the average of the components on the diagonal
            units: string specifying the units used for the frequency. Accepted values are Ha, eV (default), cm-1
        """

        w_range = np.linspace(w_min, w_max, num, endpoint=True)

        t = np.zeros((num,3,3))
        for i, w in enumerate(w_range):
            t[i] = self.tensor_at_frequency(w, units=units)

        ax, fig, plt = get_ax_fig_plt(ax)

        if 'linewidth' not in kwargs:
            kwargs['linewidth'] = 2

        if units == 'eV':
            ax.set_xlabel('Energy [eV]')
        elif units == 'Ha':
            ax.set_xlabel('Energy [Ha]')
        elif units == 'cm-1':
            ax.set_xlabel(r'Frequency [cm$^{-1}$]')

        ax.set_ylabel(r'$\varepsilon$')

        if isinstance(component, (list, tuple)):
            ax.plot(w_range, t[:,component[0], component[1]], label='[{},{}]'.format(*component), **kwargs)
        elif component == 'diag':
            for i in range(3):
                ax.plot(w_range, t[:, i, i], label='[{},{}]'.format(i,i), **kwargs)
        elif component == 'all':
            for i in range(3):
                for j in range(3):
                    ax.plot(w_range, t[:, i, j], label='[{},{}]'.format(i, j), **kwargs)
        elif component == 'diag_av':
            for i in range(3):
                ax.plot(w_range, np.trace(t, axis1=1, axis2=2)/3, label='[{},{}]'.format(i, i), **kwargs)
        else:
            ValueError('Unkwnown component {}'.format(component))

        ax.legend(loc="best")

        return fig
