# coding: utf-8
"""GSR file."""
from __future__ import print_function, division, unicode_literals, absolute_import

import numpy as np
import pymatgen.core.units as units

from collections import OrderedDict, Iterable, defaultdict
from tabulate import tabulate
from monty.string import is_string, list_strings, marquee
from monty.collections import AttrDict
from monty.functools import lazy_property
from pymatgen.core.units import EnergyArray, ArrayWithUnit
from pymatgen.entries.computed_entries import ComputedEntry, ComputedStructureEntry
from abipy.core.mixins import AbinitNcFile, Has_Structure, Has_ElectronBands, NotebookWriter
from prettytable import PrettyTable
from abipy.electrons.ebands import ElectronsReader

import logging
logger = logging.getLogger(__name__)


__all__ = [
    "GsrFile",
]


class GsrFile(AbinitNcFile, Has_Structure, Has_ElectronBands, NotebookWriter):
    """
    File containing the results of a ground-state calculation.

    Usage example:

    .. code-block:: python

        with GsrFile("foo_GSR.nc") as gsr:
            print("energy: ", gsr.energy)
            gsr.ebands.plot()
    """
    @classmethod
    def from_file(cls, filepath):
        """Initialize the object from a Netcdf file"""
        return cls(filepath)

    def __init__(self, filepath):
        super(GsrFile, self).__init__(filepath)

        self.reader = r = GsrReader(filepath)

        # Initialize the electron bands from file
        self._ebands = r.read_ebands()

        # Add forces to structure
        if self.is_scf_run:
            self.structure.add_site_property("cartesian_forces", self.cart_forces)

    def __str__(self):
        """String representation."""
        return self.to_string()

    def to_string(self, verbose=0):
        """String representation."""
        lines = []; app = lines.append

        app(marquee("File Info", mark="="))
        app(self.filestat(as_string=True))
        app("")
        app(marquee("Structure", mark="="))
        app(str(self.structure))
        if self.is_scf_run:
            app("")
            app("Stress tensor (Cartesian coordinates in Ha/Bohr**3):\n%s" % self.cart_stress_tensor)
            app("Pressure: %.3f [GPa]" % self.pressure)
        app("")
        app(self.ebands.to_string(with_structure=False, title="Electronic Bands"))

        return "\n".join(lines)

    @property
    def ebands(self):
        """:class:`ElectronBands` object."""
        return self._ebands

    @property
    def is_scf_run(self):
        """True if the GSR has been produced by a SCF run."""
        # NOTE: We use kptopt to understand if we have a SCF/NSCF run
        # In principle one should use iscf but it's not available in the GSR.
        #return self.ebands.kpoints.ksampling.kptopt >= 0
        return abs(self.cart_stress_tensor[0,0] - 9.9999999999e+99) > 0.1

    #FIXME
    @property
    def tsmear(self):
        return self.ebands.smearing.tsmear_ev.to("Ha")

    @lazy_property
    def ecut(self):
        """Cutoff energy in Hartree (Abinit input variable)"""
        return units.Energy(self.reader.read_value("ecut"), "Ha")

    @lazy_property
    def pawecutdg(self):
        """Cutoff energy in Hartree for the PAW double grid (Abinit input variable)"""
        return units.Energy(self.reader.read_value("pawecutdg"), "Ha")

    @property
    def structure(self):
        """:class:`Structure` object."""
        return self.ebands.structure

    @lazy_property
    def energy(self):
        """Total energy"""
        return units.Energy(self.reader.read_value("etotal"), "Ha").to("eV")

    @lazy_property
    def energy_per_atom(self):
        """Total energy / number_of_atoms"""
        return self.energy / len(self.structure)

    @lazy_property
    def energy_terms(self):
        return self.reader.read_energy_terms()

    @lazy_property
    def cart_forces(self):
        """Cartesian forces in eV / Ang"""
        return self.reader.read_cart_forces()

    @property
    def max_force(self):
        fmods = np.sqrt([np.dot(force, force) for force in self.cart_forces])
        return fmods.max()

    def force_stats(self, **kwargs):
        """
        Return a string with information on the forces.
        """
        fmods = np.sqrt([np.dot(force, force) for force in self.cart_forces])
        imin, imax = fmods.argmin(), fmods.argmax()

        s = "\n".join([
            "fsum: %s" % self.cart_forces.sum(axis=0),
            "mean: %s, std %s" % (fmods.mean(), fmods.std()),
            "minimum at site %s, cart force: %s" % (self.structure.sites[imin], self.cart_forces[imin]),
            "maximum at site %s, cart force: %s" % (self.structure.sites[imax], self.cart_forces[imax]),
        ])

        table = [["Site", "Cartesian Force", "Length"]]
        for i, fmod in enumerate(fmods):
            table.append([self.structure.sites[i], self.cart_forces[i], fmod])
        s += "\n" + tabulate(table)

        return s

    @lazy_property
    def cart_stress_tensor(self):
        """Stress tensor in Ha/Bohr**3"""
        return self.reader.read_cart_stress_tensor()

    @lazy_property
    def pressure(self):
        """Pressure in Gpa"""
        HaBohr3_GPa = 29421.033 # 1 Ha/Bohr^3, in GPa
        pressure = - (HaBohr3_GPa/3) * self.cart_stress_tensor.trace()
        return units.FloatWithUnit(pressure, unit="GPa", unit_type="pressure")

    @lazy_property
    def residm(self):
        """Maximum of the residuals"""
        return self.reader.read_value("residm")

    @lazy_property
    def xc(self):
        """:class:`XcFunc object with info on the exchange-correlation functional."""
        return self.reader.read_abinit_xcfunc()

    def close(self):
        self.reader.close()

    def get_computed_entry(self, inc_structure=True, parameters=None, data=None):
        """
        Returns a pymatgen :class:`ComputedStructureEntry` from the GSR file.
        Same API as the one used in vasp_output.get_computed_entry.

        Args:
            inc_structure (bool): Set to True if you want
                ComputedStructureEntries to be returned instead of ComputedEntries.
            parameters (list): Input parameters to include. It has to be one of
                the properties supported by the GSR object. If
                parameters is None, a default set of parameters that are
                necessary for typical post-processing will be set.
            data (list): Output data to include. Has to be one of the properties
                supported by the GSR object.

        Returns:

            ComputedStructureEntry/ComputedEntry
        """
        # TODO
        #param_names = {"is_hubbard", "hubbards", "potcar_symbols", "run_type"}
        if inc_structure:
            return ComputedStructureEntry(self.structure, self.energy,
                                          correction=0.0, parameters=parameters, data=data)
        else:
            return ComputedEntry(self.structure.composition, self.energy,
                                 parameters=parameters, data=data)

    def as_dict(self, **kwargs):
        # TODO: Add info depending on the run_type e.g. max_resid is NSCF
        return dict(
            structure=self.structure.as_dict(),
            final_energy=self.energy,
            final_energy_per_atom=self.energy_per_atom,
            max_force=self.max_force,
            cart_stress_tensor=self.cart_stress_tensor,
            pressure=self.pressure,
            number_of_electrons=self.nelect,
        )
            # FIXME: this call raises
            #>       if kpointcbm.label is not None:
            #E       AttributeError: 'NoneType' object has no attribute 'label'
            #ebands=self.ebands.to_pymatgen().as_dict(),
            #max_residual=
            #magnetization=self.magnetization,
            #band_gap=
            #optical_gap=
            #is_direct=
            #cbm=
            #vbm=
            #efermi=
            #band_gap:
            #optical_gap:
            #efermi:

    def write_notebook(self, nbpath=None):
        """
        Write an ipython notebook to nbpath. If nbpath is None, a temporay file in the current
        working directory is created. Return path to the notebook.
        """
        nbformat, nbv, nb = self.get_nbformat_nbv_nb(title=None)

        nb.cells.extend([
            nbv.new_code_cell("gsr = abilab.abiopen('%s')" % self.filepath),
            nbv.new_code_cell("print(gsr)"),
            nbv.new_code_cell("fig = gsr.ebands.plot()"),
            nbv.new_code_cell("fig = gsr.ebands.kpoints.plot()"),
            nbv.new_code_cell("# fig = gsr.ebands.plot_transitions(omega_ev=3.0, qpt=(0, 0, 0), atol_ev=0.1)"),
            nbv.new_code_cell("""\
if gsr.ebands.kpoints.is_ibz:
    fig = gsr.ebands.get_edos().plot()"""),
            #nbv.new_code_cell("emass = gsr.ebands.effective_masses(spin=0, band=0, acc=4)"),

        ])

        return self._write_nb_nbpath(nb, nbpath)


class EnergyTerms(AttrDict):
    """Contributions to the total GS energy. See energies_type in m_energies.F90"""

    _NAME2DOC = OrderedDict([
        # (Name, help)
        ("e_localpsp", "Local psp energy"),
        ("e_eigenvalues", "Sum of the eigenvalues - Band energy\n" +
                          "(valid for double-counting scheme dtset%optene == 1)"),
        ("e_ewald",  "Ewald energy, store also the ion/ion energy for free boundary conditions."),
        ("e_hartree", "Hartree part of the total energy"),
        ("e_corepsp", "psp core-core energy"),
        ("e_corepspdc", "psp core-core energy double-counting"),
        ("e_kinetic", "Kinetic energy part of total energy. (valid for direct scheme, dtset%optene == 0"),
        ("e_nonlocalpsp", "Nonlocal pseudopotential part of total energy."),
        ("e_entropy", "Entropy energy due to the occupation number smearing (if metal)\n" +
                      "Value is multiplied by dtset%tsmear, see %entropy for the entropy alone\n." +
                      "(valid for metals, dtset%occopt>=3 .and. dtset%occopt<=8)"),
        ("entropy", "Entropy term"),
        ("e_xc", "Exchange-correlation energy"),
        #("e_vdw_dftd2", "Dispersion energy from DFT-D2 Van der Waals correction"),
        ("e_xcdc", "enxcdc=exchange-correlation double-counting energy"),
        ("e_paw", "PAW spherical part energy"),
        ("e_pawdc", "PAW spherical part double-counting energy"),
        ("e_elecfield", "Electric enthalpy, by adding both ionic and electronic contributions"),
        ("e_magfield", "Orbital magnetic enthalpy, by adding orbital contribution"),
        ("e_fermie", "Fermie energy"),
        ("e_sicdc", "Self-interaction energy double-counting"),
        ("e_exactX", "Fock exact-exchange energy"),
        ("h0", "h0=e_kinetic+e_localpsp+e_nonlocalpsp"),
        ("e_electronpositron", "Electron-positron: electron-positron interaction energy"),
        ("edc_electronpositron", "Electron-positron: double-counting electron-positron interaction energy"),
        ("e0_electronpositron", "Electron-positron: energy only due to unchanged particles\n" +
                                "(if calctype=1, energy due to electrons only)\n" +
                                "(if calctype=2, energy due to positron only)\n"),
        ("e_monopole", "Monopole correction to the total energy for charged supercells"),
        # FIXME: Some names have been changed in Abinit8, I should recheck the code.
        #("e_xc_vdw", "vdW-DF correction to the XC energy"),
    ])

    ALL_KEYS = list(_NAME2DOC.keys())

    def __str__(self):
        return self.to_string(with_doc=False)
    __repr__ = __str__

    @property
    def table(self):
        """PrettyTable object with the results."""
        table = PrettyTable(["Term", "Value"])
        for k, doc in self._NAME2DOC.items():
            table.add_row([k, self[k]])
        return table

    def to_string(self, verbose=0, with_doc=True):
        """String representation, with documentation if with_doc."""
        lines = [str(self.table)]
        if with_doc:
            for k, doc in self._NAME2DOC.items():
                lines.append("%s: %s" % (k, doc))

        return "\n".join(lines)


class GsrReader(ElectronsReader):
    """
    This object reads the results stored in the _GSR (Ground-State Results) file produced by ABINIT.
    It provides helper function to access the most important quantities.
    """
    def read_cart_forces(self, unit="eV ang^-1"):
        """
        Read and return a numpy array with the cartesian forces in unit `unit`.
        Shape (natom, 3)
        """
        return ArrayWithUnit(self.read_value("cartesian_forces"), "Ha bohr^-1").to(unit)

    def read_cart_stress_tensor(self):
        """
        Return the stress tensor (3x3 matrix) in cartesian coordinates (Hartree/Bohr^3)
        """
        # Abinit stores 6 unique components of this symmetric 3x3 tensor:
        # Given in order (1,1), (2,2), (3,3), (3,2), (3,1), (2,1).
        c = self.read_value("cartesian_stress_tensor")
        tensor = np.empty((3, 3), dtype=np.float)
        for i in range(3): tensor[i,i] = c[i]
        for p, (i, j) in enumerate(((2,1), (2,0), (1,0))):
            tensor[i,j] = c[3+p]
            tensor[j,i] = c[3+p]

        return tensor

    def read_energy_terms(self, unit="eV"):
        """
        Return a dictionary of `Energies` with the different contributions to the total electronic energy.
        """
        convert = lambda e: units.Energy(e, unit="Ha").to(unit)
        d = {k: convert(self.read_value(k)) for k in EnergyTerms.ALL_KEYS}
        return EnergyTerms(**d)
