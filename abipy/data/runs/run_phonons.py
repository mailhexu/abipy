#!/usr/bin/env python
from __future__ import division, print_function

import os
import abipy.abilab as abilab
import abipy.data as data  

from abipy.data.runs import decorate_main

from abipy.data.runs.qptdm_workflow import *

def scf_ph_inputs():
    # Crystalline AlAs : computation of the second derivative of the total energy
    structure = data.structure_from_ucell("alas")
    pseudos = data.pseudos("13al.981214.fhi", "33as.pspnc")

    # List of q-points for the phonon calculation.
    qpoints = [
             0.00000000E+00,  0.00000000E+00,  0.00000000E+00, 
             2.50000000E-01,  0.00000000E+00,  0.00000000E+00,
             5.00000000E-01,  0.00000000E+00,  0.00000000E+00,
             2.50000000E-01,  2.50000000E-01,  0.00000000E+00,
             5.00000000E-01,  2.50000000E-01,  0.00000000E+00,
            -2.50000000E-01,  2.50000000E-01,  0.00000000E+00,
             5.00000000E-01,  5.00000000E-01,  0.00000000E+00,
            -2.50000000E-01,  5.00000000E-01,  2.50000000E-01,
            ]
    qpoints = np.reshape(qpoints, (-1,3))

    # Global variables used both for the GS and the DFPT run.
    global_vars = dict(nband=4,             
                       ecut=3.0,         
                       ngkpt=[4, 4, 4],
                       shiftk=[0, 0, 0],
                       tolvrs=1.0e-8,
                    )

    inp = abilab.AbiInput(pseudos=pseudos, ndtset=1+len(qpoints))

    inp.set_structure(structure)
    inp.set_variables(**global_vars)

    for i, qpt in enumerate(qpoints):
        # Response-function calculation for phonons.
        inp[i+2].set_variables(
            rfphon=1,        # Will consider phonon-type perturbation
            nqpt=1,          # One wavevector is to be considered
            qpt=qpt,         # This wavevector is q=0 (Gamma)
            )
            #rfatpol   1 1   # Only the first atom is displaced
            #rfdir   1 0 0   # Along the first reduced coordinate axis
            #kptopt   2     # Automatic generation of k points, taking

    # return gs_inp, ph_inputs
    return inp.split_datasets()


def ph_flow():
    workdir = "PHONONS"

    all_inps  = scf_ph_inputs()

    scf_input, ph_inputs = all_inps[0], all_inps[1:]
                                                                        
    #manager = abilab.TaskManager.from_file("taskmanager.yaml")
    manager = abilab.TaskManager.simple_mpi(mpi_ncpus=1, policy=dict(autoparal=0, max_ncpus=1))
    #manager = abilab.TaskManager.simple_mpi(mpi_ncpus=1, policy=dict(autoparal=1, max_ncpus=2))

    return phonon_flow(workdir, manager, scf_input, ph_inputs)

@decorate_main
def main():
    # Phonon Works
    flow = ph_flow()
    return flow.build_and_pickle_dump()


if __name__ == "__main__":
    import sys
    sys.exit(main())
