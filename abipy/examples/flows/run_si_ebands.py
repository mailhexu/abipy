#!/usr/bin/env python
r"""
Band structure Flow
===================

Flow for computing the band structure of silicon.
"""
from __future__ import division, print_function, unicode_literals, absolute_import

__file__ = "run_si_ebands.py"

import sys
import os
import abipy.data as abidata
import abipy.abilab as abilab
import abipy.flowtk as flowtk


def make_scf_nscf_inputs(paral_kgb=0, usepaw=0):
    """Returns two input files: GS run and NSCF on a high symmetry k-mesh."""
    pseudos = abidata.pseudos("14si.pspnc") if usepaw == 0 else data.pseudos("Si.GGA_PBE-JTH-paw.xml")

    # Get structure from cif file.
    multi = abilab.MultiDataset(structure=abidata.cif_file("si.cif"), pseudos=pseudos, ndtset=2)
    multi.set_mnemonics(True)

    # Global variables
    ecut = 6
    global_vars = dict(ecut=ecut,
                       nband=8,
                       paral_kgb=paral_kgb,
                       iomode=3,
                       timopt=-1,
                    )

    if multi.ispaw:
        global_vars.update(pawecutdg=2*ecut)

    multi.set_vars(global_vars)

    # Dataset 1 (GS run)
    multi[0].set_kmesh(ngkpt=[8, 8, 8], shiftk=[0, 0, 0])
    multi[0].set_vars(tolvrs=1e-6)

    # Dataset 2 (NSCF run)
    kptbounds = [
        [0.5, 0.0, 0.0],  # L point
        [0.0, 0.0, 0.0],  # Gamma point
        [0.0, 0.5, 0.5],  # X point
    ]

    multi[1].set_kpath(ndivsm=6, kptbounds=kptbounds)
    multi[1].set_vars(tolwfr=1e-12)

    # Generate two input files for the GS and the NSCF run
    scf_input, nscf_input = multi.split_datasets()
    return scf_input, nscf_input


def build_flow(options):
    # Working directory (default is the name of the script with '.py' removed and "run_" replaced by "flow_")
    workdir = options.workdir
    if not options.workdir:
        workdir = os.path.basename(__file__).replace(".py", "").replace("run_", "flow_")

    # Get the SCF and the NSCF input.
    scf_input, nscf_input = make_scf_nscf_inputs()

    # Build the flow.
    return flowtk.bandstructure_flow(workdir, scf_input, nscf_input, manager=options.manager)


# This block generates the thumbnails in the Abipy gallery.
# You can safely REMOVE this part if you are using this script for production runs.
if os.getenv("GENERATE_SPHINX_GALLERY", False):
    __name__ = None
    import tempfile
    options = flowtk.build_flow_main_parser().parse_args(["-w", tempfile.mkdtemp()])
    build_flow(options).plot_networkx()



@flowtk.flow_main
def main(options):
    flow = build_flow(options)
    flow.build_and_pickle_dump()
    return flow


if __name__ == "__main__":
    sys.exit(main())
