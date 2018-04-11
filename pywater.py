#!/usr/bin/env python

"""
PyWATER finds conserved water molecules in X-ray protein structure (pdb).
version 1.0

Important or conserved waters are the waters molecules which are present in most or all available pdb structures when superimposed.

Copyright 2013 Hitesh Patel and B. Gruening

Run it by following command:

GUI of the tool can be run in PyMOL as a plugin.
Steps to install in PyMOL:
    Run PyMOL as administrator.
    Install the PyWATER plugin in pymol by following the path: Plugins -> Manage Plugins -> install
    Restart the PyMol

After installation as plugin. It can be run from command in pymol 
    pywater [PDB id , Chain id [, sequence identity cutoff [, resolution cutoff [, refinement assessing method [, user defined proteins list [, linkage method [, inconsistency coefficient threshold [, degree of conservation]]]]]]]] 

    API extension:

    from pymol import cmd
    
    cmd.pywater(PDB id , Chain id [, sequence identity cutoff [, resolution cutoff [, refinement assessing method [, user defined proteins list [, linkage method [, inconsistency coefficient threshold [, degree of conservation]]]]]]])

    PDB id
            string: The PDB id of the protein for which you like to find conserved waters. {default: None}

    Chain id
            string: The chain identifier of the protein for which you like to find conserved waters in above mentioned PDB. {default: None}

    sequence identity cutoff
            string: '30', '40', '50', '70', '90', '95'or '100'. All the protein structures, clustered by BlastClust, having sequence identity more than given cutoff will be superimposed to find the conserved water molecules in query protein chain. {default: '95'} 

    resolution cutoff
            float: All the protein structures to be superimposed will be filtered first according to the structure resolution cutoff. Only structures with better resolution than given cutoff will be used further. {default: 2.0}

    refinement assessing method
            string: Choose either 'Mobility' or 'Normalized B-factor' or 'No refinement' as criteria to assess the refinement quality of crystal structure. Program will filter out the water molecules with bad refinement quality. {default: 'Mobility'}

    user defined proteins list
            string: Give a custom list of protein structures to superimpose. Specifying this list will disable 'sequence identity' and 'resolution cutoff' parameters. {default: disabled}

    linkage method
            string: Linkage method for hierarchical clustering. Choose one from single, complete, average. {default: complete}

    inconsistency coefficient threshold
            float: Any two clusters of water molecules will not be closer than given inconsistency coefficient threshold. Value ranges from 0 to 2.8. {default: 2.4} 

    degree of conservation
            float: Water molecules will be considered CONSERVED if their probability of being conserved is above given cutoff. Value ranges from 0 to 1. {default: 0.7} 

"""

import os
import glob
import shutil
import re
import collections
import tempfile
from xml.dom.minidom import parseString
import sys

if sys.version_info[0] > 2:
    import urllib.request as urllib
    from tkinter import *
    import tkinter.messagebox as tkMessageBox
    xrange = range
else:
    import urllib
    from Tkinter import *
    import tkMessageBox

import pymol.cmd as cmd
import logging

try:
    import numpy as np
except:
    sys.exit('Numpy not found')

try:
    import scipy.cluster.hierarchy as hcluster
except:
    sys.exit('Scipy not found')


# setup output directory

home_dir = os.path.expanduser("~")

outdir = os.path.join( home_dir, 'PyWATER_outdir' )
if not os.path.exists(outdir):
    os.mkdir(outdir)


# setup logging

logger = logging.getLogger('PyWATER')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler( os.path.join( outdir, 'pywater.log' ) )
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)


# initialize as PyMOL plugin
def __init__(self):
    self.menuBar.addmenuitem('Plugin', 'command',
                        'Find Conserved Waters',
                        label = 'PyWATER',
                        command = lambda: main(self.root))

# Display help messages
def pdb_id_help():
    tkMessageBox.showinfo(title = 'PDB Identifier', 
        message = "The PDB id of the protein for which you like to find conserved waters, e.g. 4lyw")

def chain_help():
    tkMessageBox.showinfo(title = 'Chain Identifier', 
        message = "The chain identifier of the protein for which you like to find conserved waters in above mentioned PDB, e.g. A.")

def seq_id_help():
    tkMessageBox.showinfo(title = 'Sequence identity cutoff', 
        message = """All the protein structures, clustered by BlastClust, having sequence identity more than given cutoff will be superimposed to find the conserved water molecules in query protein chain.
Minimum suggested Sequence identity cutoff is 95.""")

def resolution_help():
    tkMessageBox.showinfo(title = 'Structure resolution cutoff', 
        message = """All the protein structures to be superimposed will be filtered first according to the structure resolution cutoff. Only structures with better resolution than given cutoff will be used further.
Maximum suggested structure resolution cutoff is 2.5 A.""")

def refinement_quality_help():
    tkMessageBox.showinfo(title = 'Filter by refinement quality', 
        message = "Choose either Mobility or Normalized B-factor as criteria to assess the refinement quality of crystal structure. Program will filter out the water molecules with bad refinement quality.")

def user_defined_lists_help():
    tkMessageBox.showinfo(title = 'User defined pdb-chains lists',
        message = """The user defined list of pdbchains to superimpose to find conserved waters in query protein structure.
Enter the pdb chains list in format: xxxx_x,yyyy_y,zzzz_z""")

def clustering_method_help():
    tkMessageBox.showinfo(title = 'Clustering linkage method',
        message = """Choose any of the linkage method for hierarchical clustering. Default method is 'complete'.""")

def inconsistency_coefficient_help():
    tkMessageBox.showinfo(title = 'Inconsistency coefficient threshold', 
        message = """Any two clusters of water molecules will not be closer than given inconsistency coefficient threshold. The less threshold ensures each water molecule in a cluster from different structures.
Maximum suggested inconsistency coefficient threshold is 2.4 A.""")

def prob_help():
    tkMessageBox.showinfo(title = 'Degree of conservation', 
        message = """Water molecules will be considered CONSERVED if their probability of being conserved is above given cutoff.
Value ranges from 0 to 1.
Minimum suggested value is 0.5
""")

def save_sup_files_help():
    tkMessageBox.showinfo(title = 'Save superimposed files', message = """Save superimposed intermediate files.""")

# Display imput parameters

def displayInputs( selectedStruturePDB, selectedStrutureChain,
        seq_id,resolution, refinement, user_def_list,
        clustering_method, inconsistency_coefficient, prob):
    logger.info( 'Input values' )
    logger.info( 'PDB id : %s' % selectedStruturePDB)
    logger.info( 'Chain id : %s' % selectedStrutureChain)
    logger.info( 'Seqence identity cutoff : %s' % seq_id)
    logger.info( 'Structure resolution cutoff : %s' % resolution)
    logger.info( 'X-ray structure refinement assessing method : %s' % refinement)
    logger.info( 'User defined protein-chains list : %s' % user_def_list)
    logger.info( 'Hierarchical clustering linkage method : %s' % clustering_method)
    logger.info( 'Inconsistency coefficient threshold : %s' % inconsistency_coefficient)
    logger.info( 'probability cutoff : %s' % prob)

# display PyMOL session with identified conserved waters, showing H-bonds with other conserved waters, ligands or protein.
def displayInPyMOL(outdir, selectedPDBChain, atomNumbersProbDic):
    pdbCWMs = os.path.join(outdir, '%s_withConservedWaters.pdb' % selectedPDBChain)
    pdb = os.path.join(outdir, '%s.pdb' % selectedPDBChain)
    h_bond_dist = 4.0

    queryProteinCWMs = '%s_withConservedWaters' % selectedPDBChain

    cmd.load(pdbCWMs)
    cmd.orient(queryProteinCWMs)
    cmd.h_add(queryProteinCWMs)

    cmd.select('cwm_protein','polymer and %s' % queryProteinCWMs)
    cmd.select('cwm_waters','resn hoh and %s' % queryProteinCWMs)
    cmd.select('cwm_ligand','organic and %s' % queryProteinCWMs)

    cmd.select('don', '(elem n,o and (neighbor hydro)) and %s' % queryProteinCWMs)
    cmd.select('acc', '(elem o or (elem n and not (neighbor hydro))) and %s' % queryProteinCWMs)
    # h bonds between protein and conserved waters
    cmd.distance ('PW_HBA', '(cwm_protein and acc)','(cwm_waters and don)', h_bond_dist)
    cmd.distance ('PW_HBD', '(cwm_protein and don)','(cwm_waters and acc)', h_bond_dist)
    # h bonds between ligands and conserved waters
    cmd.distance ('LW_HBA', '(cwm_ligand and acc)','(cwm_waters and don)', h_bond_dist)
    cmd.distance ('LW_HBD', '(cwm_ligand and don)','(cwm_waters and acc)', h_bond_dist)
    # h bonds in between conserved waters
    cmd.distance ('HW_HBA', '(cwm_waters and acc)','(cwm_waters and don)', h_bond_dist)
    cmd.distance ('HW_HBD', '(cwm_waters and don)','(cwm_waters and acc)', h_bond_dist)

    cmd.delete('don')
    cmd.delete('acc')

    cmd.set('dash_color','yellow')
    cmd.set('dash_gap',0.3)
    cmd.set('dash_length',0.2)
    cmd.set('dash_round_ends','on')
    cmd.set('dash_width',3)

    # color and display
    cmd.util.cbam('cwm_ligand')
    cmd.show_as('sticks','cwm_ligand')

    MinDoc = min(atomNumbersProbDic.values())
    MaxDoc = max(atomNumbersProbDic.values())
    cmd.create ('conserved_waters','cwm_waters')
    for key, value in atomNumbersProbDic.items():
        cmd.alter('/conserved_waters//A/HOH`%s/O' % key, 'b=%s' % value)

    cmd.spectrum('b', 'red_blue', 'conserved_waters',minimum=MinDoc, maximum=MaxDoc)
    cmd.ramp_new('DOC', 'conserved_waters', range = [MinDoc,MaxDoc], color = '[red,blue]')
    cmd.set('sphere_scale',0.40,'conserved_waters')
    cmd.show_as('spheres','conserved_waters')

    cmd.hide('labels','*_HB*')
    cmd.remove('(hydro) and conserved_waters')
    cmd.remove('(hydro) and %s' % queryProteinCWMs)

    cmd.util.cbac('cwm_protein')
    cmd.set('transparency', 0.2)
    cmd.show('surface', 'cwm_protein')
    cmd.set('surface_color', 'gray', 'cwm_protein')

    cmd.load(pdb)
    cmd.create('all_waters', 'resn hoh and %s' % selectedPDBChain)
    cmd.color('red','ss h and %s' % selectedPDBChain)
    cmd.color('yellow','ss s and %s' % selectedPDBChain)
    cmd.color('green','ss l+ and %s' % selectedPDBChain)
    cmd.show_as('cartoon', selectedPDBChain)
    cmd.set('ray_shadows', 0)


def okMobility( pdbFile, mobilityCutoff = 2.0 ):
    """
    Check if the mobility of water molecules is acceptable. 
    Water oxygen atoms with mobility >= mobilityCutoff(default=2.0) are 
    removed from the PDB. If more than 50 % of water oxygen atoms 
    are removed than whole PDB is discarded 
    """
    normBfactors = []
    OccupancyAndBfactor = []
    for line in open(pdbFile):
        line = line.strip()
        if line.startswith('HETATM'):
            OccupancyAndBfactor.append([float(line[54:60]),float(line[60:66])])
    occupancy = [a[0] for a in OccupancyAndBfactor]
    Bfactors = [a[1] for a in OccupancyAndBfactor]
    avgB = np.mean(Bfactors)
    avgO = np.mean(occupancy)
    pdbFileLines = open(pdbFile).readlines()
    nWaters = len(pdbFileLines)-1
    logger.debug( 'Number of water molecules: %s' %nWaters )
    count = 0
    for line in reversed(pdbFileLines):
        if line.startswith('HETATM'):
            m = ((float(line[60:66])/avgB)/(float(line[54:60])/avgO))
            if m >= mobilityCutoff:
                count+=1
                pdbFileLines.remove(line)
    logger.info( 'Water oxygen atoms with a higher mobility than %s: %s: ' % (mobilityCutoff, count))
    if count > (nWaters/2):
        considerPDB = False
    elif count > 0:
            outfile = open(pdbFile,'w')
            outfile.write("".join(pdbFileLines))
            outfile.close()
            considerPDB = True
    else:
        considerPDB = True
    if considerPDB:
        logger.info( '%s is included in the prediction.' % (pdbFile))
    else:
        logger.info( '%s is excluded from the prediction.' % (pdbFile))
    return considerPDB

def okBfactor( pdbFile, normBCutoff = 1.0 ):
    """
    Check if the normalized B-factor of water molecules is acceptable.
    Water oxygen atoms with normalized B-factor >= normBCutoff(default=1.0) 
    are removed from the PDB. If more than 50 % of water 
    oxygen atoms are removed than whole PDB is discarded 
    """
    Bfactors = []
    normBfactors = []
    for line in open(pdbFile):
        line = line.strip()
        if line.startswith('HETATM'):
            Bfactors.append( float(line[60:66]) )
    avg = np.mean( Bfactors )
    stddev = np.sqrt( np.var(Bfactors) )
    pdbFileLines = open(pdbFile).readlines()
    nWaters = len(pdbFileLines) - 1
    logger.debug( 'Number of water molecules is : %s' %nWaters )
    count = 0
    for line in reversed(pdbFileLines):
        if line.startswith('HETATM'):
            normB = ( (float(line[60:66]) - avg) / stddev )
            if normB >= normBCutoff:
                count+=1
                pdbFileLines.remove(line)
    logger.info( 'water oxygen atoms having higher normalized B factor are %s: '% count)
    if count > (nWaters/2):
        considerPDB = False
    elif count > 0:
            outfile = open(pdbFile,'w')
            outfile.write("".join(pdbFileLines))
            outfile.close()
            considerPDB = True
    else:
        considerPDB = True
    logger.info( '%s is considered : %s ' % (pdbFile, considerPDB))
    return considerPDB


class Protein():
    def __init__(self, pdb_id, chain=False):
        self.pdb_id = pdb_id.lower()
        self.chain = chain.upper()
        self.pdb_id_folder = self.pdb_id[1:3]
        self.pdb_filename = self.pdb_id + '.pdb'
        self.water_coordinates = list()
        self.water_ids = list()
        self.waterIDCoordinates = {}

    def __repr__(self):
        return "%s_%s" % (self.pdb_id, self.chain)

    def calculate_water_coordinates(self, tmp_dir = False):
        path = os.path.join( tmp_dir, 'cwm_%s_Water.pdb' % self.__repr__() )
        logger.debug( 'Creating water coordinates of cwm_%s_Water.pdb.' % self.__repr__())
        for line in open(path):
            line = line.strip()
            if line.startswith('HETATM'):
                # water oxygen atom number
                key = "%s_%s" % (self.__repr__(), int(line[22:30]))
                coordinates = [ line[30:38], line[38:46], line[46:54] ]
                self.waterIDCoordinates[key] = coordinates
                self.water_coordinates.append( coordinates )
                self.water_ids.append( key )
        return self.waterIDCoordinates


class ProteinsList():
    def __init__(self, ProteinName):
        self.ProteinName = ProteinName
        self.proteins = list()
        self.selectedPDBChain = ''
        self.probability = 0.7
        self.inconsistency_coefficient = 2.0
        self.refinement = ''

    def add_protein(self, protein):
        self.proteins.add(protein)

    def add_protein_from_string(self, s):
        """
            Accepts a '1234:B' formatted string and creates a protein object out of it
            if no double point is found, it is assumed that the whole string is the pdb id
        """
        s = s.strip()
        if s.find(':') > -1:
            pdb_id, chain = s.split(':')
        else:
            pdb_id = s
            chain = False
        assert len(pdb_id) == 4, '%s is not of length 4' % pdb_id
        p = Protein(pdb_id, chain)
        self.proteins.append(p)

    def pop(self, index):
        return self.proteins.pop(index)

    def remove(self, protein):
        return self.proteins.remove(protein)

    def __iter__(self):
        for protein in self.proteins:
            yield protein

    def __len__(self):
        return len(self.proteins)

    def __getitem__( self, key ) :
        if isinstance( key, slice ) :
            # Get the start, stop, and step from the slice
            return [self.proteins[ii] for ii in xrange(*key.indices(len(self)))]
        elif isinstance( key, int ):
            # Handle negative indices
            if key < 0 :
                key += len( self.proteins )
            if key >= len( self.proteins ) :
                raise IndexError("The index (%d) is out of range." % key)
            return self.proteins[key] #Get the data from elsewhere
        else:
            raise TypeError("Invalid argument type.")


def makePDBwithConservedWaters(ProteinsList, temp_dir, outdir, save_sup_files):
    logger.info( 'Minimum desired degree of conservation is : %s' % ProteinsList.probability )
    cmd.delete('cwm_*')
    logger.info( 'Loading all pdb chains ...' )
    for protein in ProteinsList:
        cmd.load(os.path.join(temp_dir, protein.pdb_filename),'cwm_%s' % protein.pdb_id)
        cmd.remove('(hydro) and cwm_%s' % protein.pdb_id)
        cmd.select('dods','resn dod')
        cmd.alter('dods', 'resn="HOH"')
        cmd.create('cwm_%s' % protein, 'cwm_%s & chain %s' % (protein.pdb_id, protein.chain))
        cmd.delete( 'cwm_%s' % protein.pdb_id )

    logger.info( 'Superimposing all pdb chains ...' )
    for protein in ProteinsList[1:]:
        logger.info( 'Superimposing %s' % protein )
        cmd.super('cwm_%s////CA' % protein, 'cwm_%s////CA' % ProteinsList[0])
        cmd.orient( 'cwm_%s' % ProteinsList[0] )

    logger.info( 'Creating new, water only, pymol objects for each pdb chain ...' )
    for protein in ProteinsList:
        cmd.create('cwm_%s_Water' % protein, 'cwm_%s & resname hoh' % protein)

    logger.info( 'Storing water molecules and proteins in separate pdb files for each pdb chain ...' )
    for protein in ProteinsList:
        cmd.save(os.path.join(temp_dir, 'cwm_%s.pdb' % protein), 'cwm_%s' % protein)
        cmd.save(os.path.join(temp_dir, 'cwm_%s_Water.pdb' % protein), 'cwm_%s_Water' % protein)

    cmd.delete('cwm_*')

    ### filter ProteinsList by mobility or normalized B factor cutoff
    logger.debug( 'Protein chains list is %s proteins long.' % len(ProteinsList.proteins) )
    if ProteinsList.refinement != 'No refinement':
        length = len(ProteinsList.proteins)
        if ProteinsList.refinement == 'Mobility':
            logger.info( 'Filtering water oxygen atoms by mobility ...' )
            for protein in reversed(ProteinsList.proteins):
                if str(protein) != str(ProteinsList.selectedPDBChain):
                    if not okMobility(os.path.join(temp_dir, 'cwm_%s_Water.pdb' % protein)):
                        ProteinsList.proteins.remove(protein)

        if ProteinsList.refinement == 'Normalized B-factor': 
            logger.info( 'Filtering water oxygen atoms by Normalized B-factor' )
            for protein in reversed(ProteinsList.proteins):
                if str(protein) != str(ProteinsList.selectedPDBChain):
                    if not okBfactor(os.path.join(temp_dir, 'cwm_%s_Water.pdb' % protein)):
                        ProteinsList.proteins.remove(protein)

        logger.debug( 'filtered proteins chains list is %s proteins long :' % len(ProteinsList.proteins) )

    """ 
        Filtered ProteinsList
    """

    selectedPDBChain = str(ProteinsList.selectedPDBChain)
    if not os.path.exists(os.path.join(outdir,selectedPDBChain)):
        os.mkdir(os.path.join(outdir,selectedPDBChain))

    if save_sup_files:
        for file in glob.glob(os.path.join(temp_dir, 'cwm_????_?.pdb')):
            shutil.copy(file, os.path.join(outdir,selectedPDBChain))

    # Only if ProteinsList has more than one protein
    if len(ProteinsList.proteins) > 1:
        water_coordinates = list()
        waterIDCoordinates = {}
        water_ids = list()
        for protein in ProteinsList:
            protein.calculate_water_coordinates( temp_dir )
            logger.debug( 'Protein %s has %i coordinates.' % (protein, len(protein.water_coordinates)))
            water_coordinates += protein.water_coordinates
            water_ids += protein.water_ids

        if water_coordinates:
            # Only if there are any water molecules list of similar protein structures.
            logger.info( 'Number of water molecules to cluster: %i' % len(water_coordinates) )
            if len(water_coordinates) != 1:
                # Only if the total number of water molecules to cluster is less than 50000.
                if len(water_coordinates) < 50000:
                    cwm_count = 0
                    logger.info( 'Clustering the water coordinates ...' )
                    # The clustering returns a list of clusternumbers
                    # Available optoins are: single, complete, average
                    FD = hcluster.fclusterdata(water_coordinates, 
                            t = ProteinsList.inconsistency_coefficient,
                            criterion='distance', 
                            metric='euclidean',
                            depth=2,
                            method= ProteinsList.clustering_method
                        )
                    FDlist = list(FD)
                    fcDic = {}
                    for a,b in zip(water_ids,FDlist):
                        if b in fcDic:
                            fcDic[b].append(a)
                        else:
                            fcDic[b]=[a]

                    conservedWaterDic = {}
                    clusterPresenceDic = {}
                    clusterPresenceOut = open(os.path.join( outdir, selectedPDBChain, '%s_clusterPresence.txt' % selectedPDBChain ),'w')
                    clusterPresenceOut.write('Water Conservation Score'+'\t')
                    proteins_numbers = {}
                    l=0
                    for i in ProteinsList.proteins:
                        proteins_numbers[(str(i))]=l
                        l += 1
                        clusterPresenceOut.write('%s' % i +'\t')
                    clusterPresenceOut.write('\n')
                    logger.info( 'Extracting conserved waters from clusters ...' )
                    logger.debug( 'Start iterating over all clusters ...')
                    for clusterNumber, waterMols in fcDic.items():
                        logger.debug('Cluster No.: %s - Included Water Molecules: %s' % ( clusterNumber, ', '.join( waterMols ) ))
                        waterMolsNumber = len(waterMols)
                        uniquePDBs = set([a[:6] for a in waterMols])
                        uniquePDBslen = len(uniquePDBs)
                        # Update waterMols if there are two waterMolecules from same PDB is present in waterMols
                        if uniquePDBslen < waterMolsNumber:
                            logger.debug('Removed water molecules from the same protein in one cluster.')
                            waterMols.sort()
                            PDBs = [i[:6] for i in waterMols]
                            PDBsCounter = collections.Counter(PDBs)
                            for i in PDBsCounter.keys():
                                if PDBsCounter.get(i) > 1:
                                    for j in reversed(waterMols):
                                        if j[:6] == i:
                                            waterMols.remove(j)
                        c = []
                        for i in range(len(ProteinsList.proteins)):
                            for prot in proteins_numbers.keys():
                                if proteins_numbers[prot] == i:
                                    for d in waterMols:
                                        if prot == d[:6]:
                                            c.append(d)
                        waterMols = c
                        waterMolsNumber = len(waterMols)
                        uniquePDBs = set([a[:6] for a in waterMols])
                        uniquePDBslen = len(uniquePDBs)
                        probability = float(uniquePDBslen) / len(ProteinsList)
                        logger.info( 'Degree of conservation is: %s' % probability )
                        if probability >= ProteinsList.probability:
                            clusterPresenceOut.write(str(probability)+'\t')
                            k=0
                            for waterMol in waterMols:
                                sr_no = proteins_numbers[waterMol[:6]]
                                if sr_no == k:
                                    clusterPresenceOut.write(str(waterMol[7:])+'\t')
                                    k += 1
                                elif k < sr_no:
                                    for j in range(sr_no-k):
                                        clusterPresenceOut.write('NoWater'+'\t')
                                        k += 1
                                    clusterPresenceOut.write(str(waterMol[7:])+'\t')
                                    k += 1
                            for j in range(len(ProteinsList.proteins)-k):
                                clusterPresenceOut.write('NoWater'+'\t')
                            clusterPresenceOut.write('\n')

                            if selectedPDBChain in uniquePDBs:
                                cwm_count += 1
                                for waterMol in waterMols:
                                    if waterMol[:6] in conservedWaterDic:
                                        conservedWaterDic[waterMol[:6]].append('_'.join([waterMol[7:], str(probability)]))
                                    else:
                                        conservedWaterDic[waterMol[:6]] = ['_'.join([waterMol[7:], str(probability)])]
                    clusterPresenceOut.close()
                    logger.debug( 'conservedWaterDic is: ')
                    for pdb_id, atoms in conservedWaterDic.items():
                        logger.debug('Oxygen atom numbers for %s: %s' % ( pdb_id, ', '.join( atoms ) ))
                    if selectedPDBChain in conservedWaterDic.keys():
                        # save pdb file of only conserved waters for selected pdb
                        atomNumbersProbDic = {}
                        atomNumbers_Prob = conservedWaterDic[selectedPDBChain]
                        logger.info( """Degree of conservation for each conserved water molecule is stored in cwm_%s_withConservedWaters.pdb with the format 'atomNumber'_'DegreeOfConservation'""" % ( selectedPDBChain ) )
                        for probability in atomNumbers_Prob:
                            atom, prob = probability.split('_')
                            atomNumbersProbDic[ atom ] = float( prob )
                        atomNumbers = list(atomNumbersProbDic.keys())
                        selectedPDBChainConservedWatersOut = open(os.path.join(temp_dir, 'cwm_'+selectedPDBChain+'_ConservedWatersOnly.pdb'),'w+')
                        selectedPDBChainIn = open(os.path.join(temp_dir, 'cwm_'+selectedPDBChain+'_Water.pdb'))
                        for line in selectedPDBChainIn:
                            if line.startswith('HETATM'):
                                if str(int(line[22:30])) in atomNumbers:
                                    selectedPDBChainConservedWatersOut.write( line )
                        selectedPDBChainConservedWatersOut.write('END')
                        selectedPDBChainConservedWatersOut.close()

                        # add conserved waters to pdb file
                        cmd.delete('cwm_*')
                        cmd.load( os.path.join(temp_dir, 'cwm_%s.pdb' % selectedPDBChain) )
                        cmd.load( os.path.join(temp_dir, 'cwm_%s_ConservedWatersOnly.pdb' % selectedPDBChain) )
                        cmd.remove( 'resname hoh and '+'cwm_%s' % selectedPDBChain )
                        cmd.save( os.path.join(temp_dir, 'cwm_%s_withConservedWaters.pdb' % selectedPDBChain), 'cwm_*')
                        cmd.delete('cwm_*')
                        shutil.copy( os.path.join(temp_dir, 'cwm_%s_withConservedWaters.pdb' % selectedPDBChain), os.path.join(outdir,selectedPDBChain))
                        shutil.copy(os.path.join(temp_dir, 'cwm_%s.pdb' % selectedPDBChain),os.path.join(outdir,selectedPDBChain))
                        if os.path.exists(os.path.join(outdir, selectedPDBChain, 'cwm_%s_withConservedWaters.pdb' % selectedPDBChain)):
                            logger.info( "%s structure has %s conserved water molecules." % (selectedPDBChain,cwm_count))
                            displayInPyMOL(os.path.join(outdir, selectedPDBChain), 'cwm_%s' % selectedPDBChain, atomNumbersProbDic)
                        logger.info("""PDB file of query protein with conserved waters "cwm_%s_withConservedWaters.pdb" and logfile (pywater.log) is saved in %s""" % ( selectedPDBChain, os.path.abspath(outdir)))
                    else:
                        logger.info( "%s has no conserved waters" % selectedPDBChain )
                else:
                    logger.error( "%s has too many waters to cluster. Memory is not enough..." % selectedPDBChain )
            else:
                logger.info( "%s has only one water molecule..." % selectedPDBChain )
        else:
            logger.info( "%s and other structures from the same cluster do not have any water molecules." % selectedPDBChain )
    else:
        logger.error( "%s has only one PDB structure. We need atleast 2 structures to superimpose." % selectedPDBChain )


def pdbIdFormat( pdbId ):
    """
        Check whether the given PDB ID is valid or not.
    """
    if not re.compile('^[a-z0-9]{4}$').match(pdbId):
        logger.error( 'The entered PDB id %s is not valid.' % pdbId)
        tkMessageBox.showinfo(title = 'Error message', 
            message = """The entered PDB id is not valid.""")
        return False
    else:
        return True


def chainIdFormat(chainId):
    """
        Check whether the given PDB Chain ID is valid or not.
    """
    if not re.compile('^[A-Z0-9]{1}$').match(chainId):
        logger.error( 'The entered PDB chain id %s is not valid.' % chainId)
        tkMessageBox.showinfo(title = 'Error message', 
            message = """The entered PDB chain id is not valid.""")
        return False
    else:
        return True


def isXray( pdb ):
    """
        Check whether the PDB structure is determined by X-ray or not.
    """
    expInfoAddress='http://pdb.org/pdb/rest/customReport?pdbids=%s&customReportColumns=experimentalTechnique&service=wsdisplay&format=xml&ssa=n' % (pdb)
    #the PDB service API have changed
    expInfoAddress='http://www.rcsb.org/pdb/rest/customReport?pdbids=%s&customReportColumns=experimentalTechnique&service=wsdisplay&format=xml&ssa=n' % (pdb)
    
    
    expInfoURL = urllib.urlopen(expInfoAddress)
    url_string = expInfoURL.read()
    expInfoXML = parseString(url_string)
    expMethod = str(expInfoXML.getElementsByTagName('dimStructure.experimentalTechnique')[0].childNodes[0].nodeValue)
    if expMethod == 'X-RAY DIFFRACTION':
        return True
    else:
        return False

def chainPresent(pdb,chain):
    """
        Check whether the given chain id is valid for a given PDB ID.
    """
    chainInfoAddress='http://pdb.org/pdb/rest/customReport?pdbids=%s&customReportColumns=entityId&service=wsdisplay&format=xml&ssa=n' % pdb
    chainInfoURL = urllib.urlopen(chainInfoAddress)
    url_string = chainInfoURL.read()
    chainInfoXML = parseString(url_string)
    chains = [str(b.childNodes[0].nodeValue) for b in chainInfoXML.getElementsByTagName('dimEntity.chainId')]
    if chain in chains:
        return True
    else:
        return False

def fetchpdbChainsList( selectedStruture, seq_id ):
    """
        Fetch sequence cluster data from RCSB PDB for a given query protein.
    """
    pdbChainsList = []
    # http://pdb.org/pdb/rest/sequenceCluster?cluster=95&structureId=3qkl.A
    seqClustAddress = 'http://pdb.org/pdb/rest/sequenceCluster?cluster=%s&structureId=%s' % (seq_id, selectedStruture)
    seqClustURL = urllib.urlopen(seqClustAddress)
    toursurl_string= seqClustURL.read()
    if toursurl_string.startswith(b'An error has occurred'):
        return pdbChainsList
    else:
        seqCluster = parseString( toursurl_string )
        for xmlTag in seqCluster.getElementsByTagName('pdbChain'):
            pdbChain = str(xmlTag.getAttribute('name')).replace('.', ':')
            pdb = pdbChain.split(':')[0]
            if isXray(pdb):
                pdbChainsList.append(pdbChain)
        return pdbChainsList


def filterbyResolution( pdbChainsList, resolutionCutoff ):
    """
        Filter the list of PDB structures by given resolution cutoff.
    """
    pdbsList = []
    for pdbChain in pdbChainsList:
        pdbsList.append(pdbChain.split(':')[0])
    pdbsList = list( set(pdbsList) )

    filteredpdbChainsList = []
    pdbsResolution = {}
    for pdb in pdbsList:
        getResolutionAddress ='http://pdb.org/pdb/rest/customReport?pdbids=%s&customReportColumns=resolution&service=wsfile&format=xml&ssa=n' % (pdb)
        pdbsResolution_string = urllib.urlopen( getResolutionAddress ).read()
        pdbsResolutionXML = parseString( pdbsResolution_string )
        res = str(pdbsResolutionXML.getElementsByTagName('dimStructure.resolution')[0].childNodes[0].nodeValue)
        pdbsResolution[ pdb ] = res
        logger.info('Resolution of %s is: %s' % (pdb, res))

    for pdbChain in pdbChainsList:
        resolution = pdbsResolution[pdbChain.split(':')[0]]
        if resolution != 'null':
            if float(resolution) <= resolutionCutoff:
                filteredpdbChainsList.append(pdbChain)

    return filteredpdbChainsList


def FindConservedWaters(selectedStruturePDB,selectedStrutureChain,seq_id,resolution,refinement,user_def_list,clustering_method,inconsistency_coefficient,prob,save_sup_files=True):# e.g: selectedStruturePDB='3qkl',selectedStrutureChain='A'
    """
        The main function: Identification of conserved water molecules from a given protein structure.
    """
    try:
        response=urllib.urlopen('http://www.rcsb.org')
    except:
        logger.error('The PDB webserver is not reachable.')
        return None
    if not pdbIdFormat(selectedStruturePDB):
        return None
    if not isXray(selectedStruturePDB):
        logger.error( 'The entered PDB structure is not determined by X-ray crystallography.' )
        tkMessageBox.showinfo(title = 'Error message', 
            message = """The entered PDB structure is not determined by X-ray crystallography.""")
        return None
    if not chainIdFormat(selectedStrutureChain):
        return None
    if not chainPresent(selectedStruturePDB,selectedStrutureChain):
        logger.error( 'The entered PDB chain id is not valid for given PDB.' )
        tkMessageBox.showinfo(title = 'Error message', 
            message = """The entered PDB chain id is not valid for given PDB.""")
        return None
    if seq_id not in ['30', '40', '50', '70', '90', '95', '100']:
        logger.error( 'The entered sequence identity value is not valid. Please enter a value from list 30, 40, 50, 70, 90, 95 or 100' )
        tkMessageBox.showinfo(title = 'Error message', 
            message = """The entered sequence identity value is not valid. Please enter a value from list 30, 40, 50, 70, 90, 95 or 100.""")
        return None
    if resolution > 3.0:
        logger.info( 'The maximum allowed resolution cutoff is 3.0 A' )
        tkMessageBox.showinfo(title = 'Error message', 
            message = """The maximum allowed resolution cutoff is 3.0 A.""")
        return None
    UD_pdbChainsList = []
    if user_def_list != '':
        if len(user_def_list.split(',')) != 1:
            for i in user_def_list.split(','):
                if len(i.split('_')) == 2:
                    pdbid,chainid = i.split('_')[0].lower(),i.split('_')[1].upper()
                    j = ':'.join([pdbid,chainid])
                    if not pdbIdFormat(pdbid):
                        return None
                    if not chainIdFormat(chainid):
                        return None
                    else:
                        UD_pdbChainsList.append(j)
                else:
                    logger.info( 'Please enter atleast two pdb chains identifier in the format: xxxx_x,yyyy_y,zzzz_z' )
                    tkMessageBox.showinfo(title = 'Error message',
                        message = """Please enter atleast two pdb chains identifier in the format: xxxx_x,yyyy_y,zzzz_z""")
                    return None
        else:
            logger.info( 'Please enter atleast two pdb chains identifier in the format: xxxx_x,yyyy_y,zzzz_z' )
            tkMessageBox.showinfo(title = 'Error message', 
                message = """Please enter atleast two pdb chains identifier in the format: xxxx_x,yyyy_y,zzzz_z""")
            return None
    if inconsistency_coefficient > 2.8:
        logger.info( 'The maximum allowed inconsistency coefficient threshold is 2.8 A' )
        tkMessageBox.showinfo(title = 'Error message', 
            message = """The maximum allowed inconsistency coefficient threshold is 2.8 A.""")
        return None
    if prob > 1.0 or prob < 0.4:
        logger.info( 'The degree of conservation is allowed from 0.4 A to 1.0 A.' )
        tkMessageBox.showinfo(title = 'Error message', 
            message = """The degree of conservation is allowed from 0.4 A to 1.0 A.""")
        return None
    online_pdb_db = 'http://www.pdb.org/pdb/files/%s.pdb'
    displayInputs(selectedStruturePDB,selectedStrutureChain,seq_id,resolution,refinement,user_def_list,clustering_method,inconsistency_coefficient,prob)

    tmp_dir = tempfile.mkdtemp()

    selectedStruture = ".".join([selectedStruturePDB.lower(),selectedStrutureChain.upper()]) # 3qkl.A
    up = ProteinsList(ProteinName = selectedStruture) # ProteinsList class instance up
    up.refinement = refinement
    up.probability = prob
    up.clustering_method = clustering_method
    up.inconsistency_coefficient = inconsistency_coefficient
    logger.info( 'selectedStruture is : %s' % selectedStruture )
    up.selectedPDBChain = Protein(selectedStruturePDB, selectedStrutureChain) # up.selectedPDBChain = 3qkl_a
    logger.info( 'up selectedPDBChain is : %s' % up.selectedPDBChain )
    selectedPDBChain = str(up.selectedPDBChain)
    logger.info( 'selectedPDBChain name is : %s' % selectedPDBChain )
    if UD_pdbChainsList == []:
        logger.info( """Fetching protein chains list from PDB clusters ...
        This cluster contains: """ )
        pdbChainsList = fetchpdbChainsList(selectedStruture,seq_id) # ['3QKL:A', '4EKL:A', '3QKM:A', '3QKK:A', '3OW4:A', '3OW4:B', '3OCB:A', '3OCB:B', '4EKK:A', '4EKK:B']
        logger.info( 'Protein chains list contains %i pdb chains: "%s"' % (len(pdbChainsList), ', '.join(pdbChainsList)))
        logger.info( 'Filtering by resolution ...')
        pdbChainsList = filterbyResolution(pdbChainsList,resolution)
        # make sure query structure is not filtered out
        queryStr = ':'.join(selectedStruture.upper().split('.'))
        if queryStr in pdbChainsList:
            pdbChainsList.remove(queryStr)
            pdbChainsList.insert(0,queryStr)
        if queryStr not in pdbChainsList:
            pdbChainsList.insert(0,queryStr)
        # Added again If query structure filtered out..
        logger.info( 'Filtered protein chains list contains %i pdb chains: "%s"' % (len(pdbChainsList), ', '.join(pdbChainsList)) )
    else:
        pdbChainsList = UD_pdbChainsList
    for pdbChain in pdbChainsList:
        up.add_protein_from_string(pdbChain)

    if len(up.proteins)>1:
        for protein in up:
            if not os.path.exists(os.path.join(tmp_dir, '%s.pdb' % protein.pdb_id)):
                logger.info( 'Retrieving structure: %s' % protein.pdb_id)
                urllib.urlretrieve(online_pdb_db % protein.pdb_id.upper(), os.path.join(tmp_dir, protein.pdb_id+'.pdb'))
        logger.info( 'Save PDB file with conserved water molecules ...' )
        makePDBwithConservedWaters(up, tmp_dir, outdir, save_sup_files)
    else:
        logger.info( "%s has only one PDB structure. We need atleast 2 structures to superimpose." % selectedPDBChain)
    shutil.rmtree(tmp_dir)


class ConservedWaters( Frame ):
    """
        Creates PyMOL plugin GUI
    """
    def __init__(self, parent):
        Frame.__init__(self, parent, background="white")
        self.parent=parent
        self.parent.title("PyWATER - Find Conserved Waters")
        self.grid()
        self.makeWindow()

    def varcheck(self, var, E1, E2, O1):
        if var.get() == 0:
            E1.configure(state='disabled')
            E2.configure(state='normal')
            O1.configure(state='normal')
        else:
            E1.configure(state='normal')
            E2.configure(state='disabled')
            O1.configure(state='disabled')

    def makeWindow(self):
        frame1 = Frame(self.parent)
        frame1.grid()

        Label(frame1, text="PDB id").grid(row=0, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=pdb_id_help).grid(row=0, column=2, sticky=W)
        v1 = StringVar(master=frame1)
        v1.set('')
        Entry(frame1,textvariable=v1).grid(row=0, column=1, sticky=W)

        Label(frame1, text="Chain id").grid(row=0, column=3, sticky=W)
        Button(frame1,text=" Help  ",command=chain_help).grid(row=0, column=5, sticky=W)
        v2 = StringVar(master=frame1)
        v2.set('')
        Entry(frame1,textvariable=v2).grid(row=0, column=4, sticky=W)

        Label(frame1, text="Sequence identity cutoff").grid(row=1, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=seq_id_help).grid(row=1, column=2, sticky=W)
        v3 = StringVar(master=frame1)
        v3.set("95")
        O1 = OptionMenu(frame1, v3, '30', '40', '50', '70', '90', '95', '100')
        O1.grid(row=1, column=1, sticky=W)

        Label(frame1, text="Structure resolution cutoff").grid(row=2, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=resolution_help).grid(row=2, column=2, sticky=W)
        v4 = StringVar(master=frame1)
        v4.set("2.0")
        E2 = Entry(frame1,textvariable=v4)
        E2.grid(row=2, column=1, sticky=W)

        Label(frame1, text="Refinement assessing method").grid(row=5, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=refinement_quality_help).grid(row=5, column=2, sticky=W)
        v5 = StringVar(master=frame1)
        v5.set('Mobility')
        OptionMenu(frame1, v5, 'Mobility', 'Normalized B-factor','No refinement').grid(row=5, column=1, sticky=W)

        v6 = StringVar(master=frame1)
        v6.set('')
        E1 = Entry(frame1,textvariable=v6,state=DISABLED)
        E1.grid(row=2, column=3, columnspan=2, rowspan=2, sticky=W+E+N+S)

        var = IntVar(master=frame1)
        Checkbutton(frame1, text="User defined pdb-chains list", variable=var,command=lambda: self.varcheck(var,E1,E2,O1)).grid(row=1, column=3, sticky=W)
        Button(frame1,text=" Help  ",command=user_defined_lists_help).grid(row=1, column=5, sticky=W)

        Label(frame1, text="Clustering method").grid(row=6, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=clustering_method_help).grid(row=6, column=2, sticky=W)
        v7 = StringVar(master=frame1)
        v7.set("complete")
        OptionMenu(frame1, v7, 'complete', 'average', 'single').grid(row=6, column=1, sticky=W)

        Label(frame1, text="Inconsistency coefficient threshold").grid(row=7, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=inconsistency_coefficient_help).grid(row=7, column=2, sticky=W)
        v8 = StringVar(master=frame1)
        v8.set("2.4")
        Entry(frame1,textvariable=v8).grid(row=7, column=1, sticky=W)

        Label(frame1, text="Degree of conservation").grid(row=8, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=prob_help).grid(row=8, column=2, sticky=W)
        v9 = StringVar(master=frame1)
        v9.set("0.7")
        Entry(frame1,textvariable=v9).grid(row=8, column=1, sticky=W)

        frame2 = Frame(self.parent)
        frame2.grid()

        v10 = BooleanVar(master=frame2)
        Checkbutton(frame2, text="Save superimposed pdb files", variable=v10, onvalue = True, offvalue = False).grid(row=0, column=1, sticky=W)
        v10.set(False)
        Button(frame2,text=" Help ", command = save_sup_files_help ).grid(row=0, column=2, sticky=W)

        Button(frame2,text=" Find Conserved Water Molecules ",
                command = lambda: FindConservedWaters(
                    str(v1.get()).lower(),
                    str(v2.get()).upper(),
                    str(v3.get()),
                    float(v4.get()),
                    str(v5.get()),
                    str(v6.get()),
                    str(v7.get()),
                    float(v8.get()),
                    float(v9.get()),
                    bool(v10.get())
                )
            ).grid(row=1, column=1, sticky=W)


def toPyWATER( v1, v2, v3 = '95', v4 = 2.0, v5 = 'Mobility', v6 = '', v7 = 'complete', v8 = 2.0, v9 = 0.7):
    """
        Convert data types of input parameters given by command line.
    """
    selectedStruturePDB = str(v1).lower()
    selectedStrutureChain = str(v2).upper()
    seq_id = str(v3)
    resolution = float(v4)
    refinement = str(v5)
    user_def_list = str(v6)
    clustering_method = str(v7)
    inconsistency_coefficient = float(v8)
    prob = float(v9)
    FindConservedWaters(selectedStruturePDB,selectedStrutureChain,seq_id,resolution,refinement,user_def_list,clustering_method,inconsistency_coefficient,prob)


def main(parent=None):
    root = Toplevel(parent)
    app = ConservedWaters(root)


#Extends PyMOL API to use this tool from command line.
cmd.extend('pywater', toPyWATER)


if __name__ == '__main__':
    main()

