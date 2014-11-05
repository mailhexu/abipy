#!/usr/bin/env python
"""Phonon band structure of AlAs."""
from __future__ import division, print_function

import sys
import os
import numpy as np
import abipy.abilab as abilab
import abipy.data as abidata

from abipy.core.structure import Structure
from pymatgen.io.abinitio.abiobjects import AbiStructure
from pymatgen.io.gwwrapper.helpers import s_name
from pymatgen.io.abinitio.pseudos import PseudoTable


def scf_ph_inputs(structure, options):
    """
    This function constructs the input files for the phonon calculation: 
    GS input + the input files for the phonon calculation.
    """

    abi_pseudo = os.environ['ABINIT_PS_EXT']
    abi_pseudo_dir = os.environ['ABINIT_PS']
    pseudos = []
    for element in structure.composition.element_composition:
        pseudo = os.path.join(abi_pseudo_dir, str(element) + abi_pseudo)
        pseudos.append(pseudo)
    pseudos = PseudoTable(pseudos)

    qptbounds = structure.calc_kptbounds()
    qptbounds = np.reshape(qptbounds, (-1, 3))
    print(qptbounds)
    ng2qpt = structure.calc_ngkpt(2)
    print(ng2qpt)

    # List of q-points for the phonon calculation.
    qpoints = [
             0.00000000E+00,  0.00000000E+00,  0.00000000E+00, 
             2.50000000E-01,  0.00000000E+00,  0.00000000E+00,
             5.00000000E-01,  0.00000000E+00,  0.00000000E+00,
             2.50000000E-01,  2.50000000E-01,  0.00000000E+00,
             5.00000000E-01,  2.50000000E-01,  0.00000000E+00,
            -2.50000000E-01,  2.50000000E-01,  0.00000000E+00,
             5.00000000E-01,  5.00000000E-01,  0.00000000E+00,
             0.00000000E+00,  0.00000000E+00,  2.50000000E-01,
            -2.50000000E-01,  5.00000000E-01,  2.50000000E-01,
            ]
    qpoints = np.reshape(qpoints, (-1,3))

    # Global variables used both for the GS and the DFPT run.
    global_vars = dict(nband=4,             
                       ecut=3.0,         
                       ngkpt=[4, 4, 4],
                       shiftk=[0, 0, 0],
                       tolvrs=1.0e-8,
                       paral_kgb=0,
                       )

    global_vars.update(options)

    ngkpt = global_vars['ngkpt']
    ngkpt = 3*[ngkpt] if not isinstance(ngkpt, list) else ngkpt
    global_vars['ngkpt'] = ngkpt

    inp = abilab.AbiInput(pseudos=pseudos, ndtset=1+len(qpoints))

    inp.set_structure(structure)
    inp.set_variables(**global_vars)

    for i, qpt in enumerate(qpoints):
        # Response-function calculation for phonons.
        inp[i+2].set_variables(
            nstep=20,
            rfphon=1,        # Will consider phonon-type perturbation
            nqpt=1,          # One wavevector is to be considered
            qpt=qpt,         # This wavevector is q=0 (Gamma)
            )

            #rfatpol   1 1   # Only the first atom is displaced
            #rfdir   1 0 0   # Along the first reduced coordinate axis
            #kptopt   2      # Automatic generation of k points, taking

    # Split input into gs_inp and ph_inputs
    return inp.split_datasets()


def run_annaddb(flow, structure):

    #structure = flow[0][0].
    manager = abilab.TaskManager.from_user_config()

    # We should have a DDB files with IFC(q) in work.outdir
    ddb_files = []
    for work in flow[1:]:
        ddbs = work.outdir.list_filepaths(wildcard="*DDB")
        assert len(ddbs) == 1
        ddb_files.append(ddbs[0])

    # TODO: Check automatic restart
    assert all(work.finalized for work in flow)
    assert flow.all_ok

    # Merge the DDB files
    out_ddb = flow.outdir.path_in("flow_DDB")
    ddb_path = abilab.Mrgddb().merge(ddb_files, out_ddb=out_ddb, description="DDB generated by %s" % __file__,
                                     cwd=flow.outdir.path)
    assert ddb_path == out_ddb

    # Build new workflow with Anaddb tasks.
    # Construct a manager with mpi_ncpus==1 since  anaddb do not support mpi_ncpus > 1 (except in elphon)
    shell_manager = manager.to_shell_manager()
    awork = abilab.Workflow(manager=shell_manager)

    # Phonons bands and DOS with gaussian method
    anaddb_input = abilab.AnaddbInput.phbands_and_dos(
        structure, ngqpt=(4, 4, 4), ndivsm=5, nqsmall=10, dos_method="gaussian: 0.001 eV")

    atask = abilab.AnaddbTask(anaddb_input, ddb_node=ddb_path, manager=shell_manager)
    awork.register(atask)

    # Phonons bands and DOS with tetrahedron method
    anaddb_input = abilab.AnaddbInput.phbands_and_dos(
        structure, ngqpt=(4, 4, 4), ndivsm=5, nqsmall=10, dos_method="tetra")

    atask = abilab.AnaddbTask(anaddb_input, ddb_node=ddb_path, manager=shell_manager)
    awork.register(atask)

    flow.register_work(awork)
    flow.allocate()
    flow.build()

    for i, atask in enumerate(awork):
        print("about to run anaddb task: %d" % i)
        atask.start_and_wait()
        assert atask.status == atask.S_DONE
        atask.check_status()
        assert atask.status == atask.S_OK

        # TODO: output files are not produced in outdir
        #assert len(atask.outdir.list_filepaths(wildcard="*PHBST.nc")) == 1
        #assert len(atask.outdir.list_filepaths(wildcard="*PHDOS.nc")) == 1


def build_flow(structure, workdir, options):
    """
    Create an `AbinitFlow` for phonon calculations:

        1) One workflow for the GS run.

        2) nqpt workflows for phonon calculations. Each workflow contains 
           nirred tasks where nirred is the number of irreducible phonon perturbations
           for that particular q-point.
    """

    # Instantiate the TaskManager.
    manager = abilab.TaskManager.from_user_config()

    all_inps = scf_ph_inputs(structure, options)
    scf_input, ph_inputs = all_inps[0], all_inps[1:]

    return abilab.phonon_flow(workdir, manager, scf_input, ph_inputs)


class NotReady(Exception):
    """
    previous flow is not complete
    """


#@abilab.flow_main
def main():

    options = {}

    cifs = [f for f in os.listdir('.') if 'cif' in f]
    convtests = {'ecut': [4, 8, 12], 'ngkpt': [4, 6, 8]}

    for cif in cifs:
        structure = Structure.from_file(cif)
        #structure = AbiStructure.asabistructure(structure)
        structure.item = cif
        for convtest in convtests:
            for value in convtests[convtest]:

                workdir = '%s_%s_%s' % (s_name(structure), str(convtest), str(value))

                try:
                    flow = abilab.AbinitFlow.pickle_load(workdir)
                    if not flow.all_ok:
                        raise NotReady
                    run_annaddb(flow=flow, structure=structure)
                except NotReady:
                    pass
                except (IOError, OSError):
                    options[convtest] = value
                    flow = build_flow(structure=structure, workdir=workdir, options=options)
                    flow.build_and_pickle_dump()


if __name__ == "__main__":
    main()
