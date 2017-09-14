# coding: utf-8
"""Test for output files"""
from __future__ import unicode_literals, division, print_function

import os
import abipy.data as abidata

from abipy import abilab
from abipy.core.testing import AbipyTest
from abipy.abio.outputs import AbinitOutputFile, AbinitLogFile


class AbinitLogFileTest(AbipyTest):

    def test_abinit_logfile(self):
        """"Testing AbinitLogFile."""
        log_path = abidata.ref_file("refs/abinit.log")
        with AbinitLogFile(log_path) as abilog:
            repr(abilog); str(abilog)
            assert len(abilog.events) == 2
            if self.has_nbformat():
                abilog.write_notebook(nbpath=self.get_tmpname(text=True))


class AbinitOutputTest(AbipyTest):

    def test_gs_output(self):
        """Testing AbinitOutputFile with GS calculation."""
        abo_path = abidata.ref_file("refs/si_ebands/run.abo")
        with AbinitOutputFile(abo_path) as abo:
            repr(abo); str(abo)
            assert abo.to_string(verbose=2)

            assert abo.version == "8.0.6"
            assert abo.run_completed
            assert not abo.dryrun_mode
            assert abo.ndtset == 2
            assert abo.has_same_initial_structures
            assert abo.has_same_final_structures
            assert len(abo.initial_structures) == 2
            assert abo.initial_structure is not None
            assert abo.initial_structure.abi_spacegroup is not None
            assert abo.initial_structure == abo.final_structure
            abo.diff_datasets(1, 2, dryrun=True)

            print(abo.events)
            gs_cycle = abo.next_gs_scf_cycle()
            assert gs_cycle is not None
            if self.has_matplotlib():
                gs_cycle.plot(show=False)
            abo.seek(0)
            assert abo.next_d2de_scf_cycle() is None

            timer = abo.get_timer()
            assert len(timer) == 1
            assert str(timer.summarize())

            if self.has_matplotlib():
                abo.compare_gs_scf_cycles([abo_path], show=False)
                timer.plot_all(show=False)
                abo.plot(show=False)

            if self.has_nbformat():
                abo.write_notebook(nbpath=self.get_tmpname(text=True))
                timer.write_notebook(nbpath=self.get_tmpname(text=True))

    def test_ph_output(self):
        """Testing AbinitOutputFile with phonon calculations."""
        abo_path = abidata.ref_file("refs/gs_dfpt.abo")
        with AbinitOutputFile(abo_path) as abo:
             repr(abo); str(abo)
             assert abo.to_string(verbose=2)

             assert abo.version == "8.3.2"
             assert abo.run_completed
             assert not abo.dryrun_mode
             assert abo.ndtset == 3
             assert abo.has_same_initial_structures
             assert abo.has_same_final_structures
             assert len(abo.initial_structures) == 3
             assert abo.initial_structure is not None
             assert abo.initial_structure.abi_spacegroup is not None
             assert abo.initial_structure == abo.final_structure

             gs_cycle = abo.next_gs_scf_cycle()
             assert gs_cycle is not None
             ph_cycle = abo.next_d2de_scf_cycle()
             assert ph_cycle is not None
             if self.has_matplotlib():
                ph_cycle.plot(show=False)
                abo.compare_d2de_scf_cycles([abo_path], show=False)
                abo.plot(show=False)

             if self.has_nbformat():
                abo.write_notebook(nbpath=self.get_tmpname(text=True))

    def test_dryrun_output(self):
        """Testing AbinitOutputFile with file produced in dry-run mode."""
        with abilab.abiopen(abidata.ref_file("refs/dryrun.abo")) as abo:
            repr(abo); str(abo)
            assert abo.to_string(verbose=1)
            assert abo.dryrun_mode
            assert abo.ndtset == 1
            assert abo.has_same_initial_structures
            assert abo.has_same_final_structures
            assert len(abo.initial_structures) == 1

            assert abo.initial_structure.abi_spacegroup is not None

    def test_all_outputs_in_tests(self):
        """
        Try to parse all Abinit output files inside the Abinit `tests` directory.
        Requires $ABINIT_HOME_DIR env variable.
        """
        abi_homedir = os.environ.get("ABINIT_HOME_DIR")
        if abi_homedir is not None:
            #raise self.SkipTest("Environment variable `ABINIT_HOME_DIR` is required for this test.")
            abitests_dir = os.path.join(abi_homedir, "tests")
        else:
            abitests_dir = os.path.join(abidata.dirpath, "refs")

        from abipy.abio.outputs import validate_output_parser
        assert os.path.exists(abitests_dir)
        retcode = validate_output_parser(abitests_dir=abitests_dir)
        assert retcode == 0
