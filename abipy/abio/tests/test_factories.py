# coding: utf-8
from __future__ import unicode_literals, division, print_function

import sys
import abipy.data as abidata  
import abipy.abilab as abilab
from pprint import pprint
from abipy.core.testing import AbipyTest
from abipy.abio.inputs import AbinitInput, MultiDataset
from abipy.abio.factories import *


class FactoryTest(AbipyTest):

    def setUp(self):
        # Si ebands
        self.si_structure = abilab.Structure.from_file(abidata.cif_file("si.cif"))
        self.si_pseudo = abidata.pseudos("14si.pspnc")

    def validate_inp(self, inp):
        # Hack neede because ecut is not in the pseudos.
        inp.set_vars(ecut=3)

        #v = inp.abivalidate()
        #if v.retcode != 0:
        #    raise RuntimeError(v.err)
        #else:
        #    print("Valid input!")

        # Test validity of individual datasets.
        for dtset in inp.split_datasets():
            v = dtset.abivalidate()

    def test_factory_protocol(self):
        """Testing factory protocol."""
        # XXX

        # No ecut and pseudos without hints 
        #with self.assertRaises(AbinitInput.Error):
        #    ebands_input(self.si_structure, pseudos=abidata.pseudos("14si.pspnc", "Si.oncvpsp"))

    def test_ebands_input(self):
        """Testing ebands_input factory."""
        inp = ebands_input(self.si_structure, self.si_pseudo, kppa=10, ecut=2)
        self.validate_inp(inp)

        scf_inp, nscf_inp = inp.split_datasets()

        #inp = ebands_input(self.si_structure, self.si_pseudo, scf_kppa, nscf_nband, dos_kppa=dos_kppa)
        #print(inp)
        #self.validate_inp(inp)

        #return
        flow = abilab.Flow("flow_ebands_input")
        flow.register_work(abilab.BandStructureWork(scf_inp, nscf_inp))
        flow.allocate()
        #flow.make_scheduler().start()

    def test_ion_ioncell_relax_input(self):
        """Testing ioncell_relax_input factory."""
        inp = ion_ioncell_relax_input(self.si_structure, self.si_pseudo, kppa=10, ecut=2)
                            #scf_kppa, scf_nband #accuracy="normal", spin_mode="polarized",
                            #smearing="fermi_dirac:0.1 eV", charge=0.0, scf_algorithm=None)

        self.validate_inp(inp)
        ion_inp, ioncell_inp = inp.split_datasets()

        #return
        flow = abilab.Flow("flow_ion_ioncell_relax_input")
        flow.register_work(abilab.RelaxWork(ion_inp, ioncell_inp))
        flow.allocate()
        #flow.make_scheduler().start()

    def test_g0w0_with_ppmodel_inputs(self):
        """Testing g0w0_with_ppmodel_input factory."""
        scf_kppa, scf_nband, nscf_nband = 10, 10, 10
        ecuteps, ecutsigx = 2, 2


        multi = g0w0_with_ppmodel_inputs(self.si_structure, self.si_pseudo, scf_kppa, nscf_nband, ecuteps, ecutsigx,
                                      ecut=2)
                                      #accuracy="normal", spin_mode="polarized", smearing="fermi_dirac:0.1 eV",
                                      #ppmodel="godby", charge=0.0, scf_algorithm=None, inclvkb=2, scr_nband=None,
                                      #sigma_nband=None, gw_qprange=1):

        self.validate_inp(multi)
        
        #return
        scf_input, nscf_input, scr_input, sigma_input = multi.split_datasets()
        flow = abilab.Flow("flow_g0w0_with_ppmodel")
        flow.register_work(abilab.G0W0Work(scf_input, nscf_input, scr_input, sigma_input))
        flow.allocate()
        #flow.make_scheduler().start()

    def test_convergence_inputs_single(self):
        """Testing g0w0_convergence_input factory single calculation."""
        scf_kppa, scf_nband, nscf_nband = 10, 10, [10]
        ecuteps, ecutsigx = [2], 2

        inputs = g0w0_convergence_inputs(self.si_structure, self.si_pseudo, scf_kppa, nscf_nband, ecuteps, ecutsigx,
                                         ecut_s=[2], scf_nband=scf_nband)
        # accuracy="normal", spin_mode="polarized", smearing="fermi_dirac:0.1 eV",
        # ppmodel="godby", charge=0.0, scf_algorithm=None, inclvkb=2, scr_nband=None,
        # sigma_nband=None, gw_qprange=1):

        # one scf, one nscf and one screening / sigma multi
        self.assertEqual(len(inputs), 4)
        self.assertIsInstance(inputs[0][0], AbinitInput)
        self.assertIsInstance(inputs[1], AbinitInput)
        self.assertIsInstance(inputs[2][0], AbinitInput)
        self.assertIsInstance(inputs[3][0], AbinitInput)

        self.assertEqual(hash(inputs[0][0]), -8771227605666062967)
        self.assertEqual(hash(inputs[1]), -1345233524349244896)
        self.assertEqual(hash(inputs[2][0]), 5673011933089823371)
        self.assertEqual(hash(inputs[3][0]), 995786873757779158)

        #val = inputs[0][0].abivalidate()
        #print(val.retcode)
        #self.assertEqual(val.retcode, 0)

        for input in [item for sublist in inputs for item in sublist]:
            val = input.abivalidate()
            print(val.retcode)
            self.assertEqual(val.retcode, 127)

        inputs[1].abivalidate()
        inputs[2][0].abivalidate()
        inputs[3][0].abivalidate()

        self.assertEqual(len(inputs[0][0].to_string()), 3153)
        self.assertEqual(len(inputs[1][0].to_string()), 3153)
        self.assertEqual(len(inputs[2][0].to_string()), 3153)
        self.assertEqual(len(inputs[3][0].to_string()), 3153)
        self.assertEqual(inputs[0][0]['gwpara'], 2)
        self.assertEqual(inputs[0][0]['gwmem'], '10')
        self.assertEqual(inputs[0][0]['optdriver'], 3)
        self.assertEqual(inputs[0][0]['optdriver'], 4)

        done = False
        self.assertTrue(done)

        for multi in multis:
            self.validate_inp(multi)

    def test_convergence_inputs_conve(self):
        """Testing g0w0_convergence_input factory single calculation."""
        scf_kppa, scf_nband, nscf_nband = 10, 10, [10, 12, 14]
        ecuteps, ecutsigx = [2, 3, 4], 2

    def test_bse_with_mdf(self):
        """Testing bse_with_mdf input factory."""

        scf_kppa, scf_nband, nscf_nband, dos_kppa = 10, 10, 10, 4
        ecuteps, ecutsigx = 3, 2
        nscf_ngkpt, nscf_shiftk = [2,2,2], [[0,0,0]]

        multi = bse_with_mdf_inputs(self.si_structure, self.si_pseudo, scf_kppa, nscf_nband, nscf_ngkpt, nscf_shiftk,
                                    ecuteps=2, bs_loband=1, bs_nband=2, mbpt_sciss="0.1 eV", mdf_epsinf=12, ecut=2)
                                    #exc_type="TDA", bs_algo="haydock", accuracy="normal", spin_mode="polarized", 
                                    #smearing="fermi_dirac:0.1 eV", charge=0.0, scf_algorithm=None):

        print(multi)
        self.validate_inp(multi)
        #return
        scf_input, nscf_input, bse_input = multi.split_datasets()
        flow = abilab.Flow("flow_bse_with_mdf")
        flow.register_work(abilab.BseMdfWork(scf_input, nscf_input, bse_input))
        flow.allocate()
        #flow.make_scheduler().start()

    def test_scf_phonons_inputs(self):
        """Testing scf_phonons_inputs."""
        scf_kppa, scf_nband, nscf_nband, dos_kppa = 10, 10, 10, 4
        ecut = 4
        inps = scf_phonons_inputs(self.si_structure, self.si_pseudo, scf_kppa,
                                  ecut=ecut) #, pawecutdg=None, scf_nband=None, accuracy="normal", spin_mode="polarized",
        print(inps[0])
        print(inps[1])
        #return 
        #for inp in inps:
        #    self.validate_inp(inp)

        if self.has_abinit():
            print(inps[1].abiget_irred_phperts())
        #assert 0


if __name__ == '__main__':
    import unittest
    unittest.main()
