#!/usr/bin/env python

"""
PyCWMs is a tool to find important or conserved waters in X-ray protein structure (pdb).
version 1.0

Important or conserved waters are the waters molecules which are present in most or all available pdb structures when superimposed.

Copyright 2013 Hitesh Patel and B. Gruening

Run it by following command:

GUI of the tool can be run in PyMOL as a plugin.
Steps to install in PyMOL:
    Run PyMOL as administrator.
    Install the PyCWMs plugin in pymol by following the path: Plugins -> Manage Plugins -> install
    Restart the PyMol

After installation as plugin. It can be run from command in pymol 
    pycwms [PDB id , Chain id [, sequence identity cutoff [, resolution cutoff [, refinement assessing method [, inconsistency coefficient threshold [, degree of conservation]]]]]] 

    API extension:

    cmd.pycwms(PDB id , Chain id [, sequence identity cutoff [, resolution cutoff [, refinement assessing method [, inconsistency coefficient threshold [, degree of conservation]]]]])

    PDB id
            string: The PDB id of the protein for which you like to find conserved waters. {default: None}

    Chain id
            string: The chain identifier of the protein for which you like to find conserved waters in above mentioned PDB. {default: None}

    sequence identity cutoff
            string: '30', '40', '50', '70', '90', '95'or '100'. All the protein structures, clustered by BlastClust, having sequence identity more than given cutoff will be superimposed to find the conserved water molecules in query protein chain. {default: '95'} 

    resolution cutoff
            float: All the protein structures to be superimposed will be filtered first according to the structure resolution cutoff. Only structures with better resolution than given cutoff will be used further. {default: 2.0}

    refinement assessing method
            string: Choose either 'Mobility' or 'Normalized B-factor' as criteria to assess the refinement quality of crystal structure. Program will filter out the water molecules with bad refinement quality. {default: 'Mobility'}

    inconsistency coefficient threshold
            float: Any two clusters of water molecules will not be closer than given inconsistency coefficient threshold. Value ranges from 0 to 2.4. {default: 2.0} 

    degree of conservation
            float: Water molecules will be considered CONSERVED if their probability of being conserved is above given cutoff. Value ranges from 0 to 1. {default: 0.7} 



"""

import os
import urllib
import shutil
import re
import tempfile
from xml.dom.minidom import parseString
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
    sys.exit('Scipy  not found')


# setup output directory

home_dir = os.path.expanduser("~")

outdir = os.path.join( home_dir, 'PyCWMs_outdir' )
if not os.path.exists(outdir):
    os.mkdir(outdir)


# setup logging

logger = logging.getLogger('PyCWMs')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler( os.path.join( outdir, 'pycwms.log' ) )
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
                        label = 'PyCWMs',
                        command = main)

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
    tkMessageBox.showinfo(title = 'Filter by refinement quality', message = "Choose either Mobility or Normalized B-factor as criteria to assess the refinement quality of crystal structure. Program will filter out the water molecules with bad refinement quality.")

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


# Display imput parameters
def displayInputs(selectedStruturePDB, selectedStrutureChain, seq_id, resolution, inconsistency_coefficient, prob):
    logger.info( 'Input values' )
    logger.info( 'PDB id : ' + selectedStruturePDB)
    logger.info( 'Chain id : %s' % selectedStrutureChain)
    logger.info( 'Seqence identity cutoff : %s' % seq_id)
    logger.info( 'Structure resolution cutoff : %s' % resolution)
    logger.info( 'Inconsistency coefficient threshold : %s' % inconsistency_coefficient)
    logger.info( 'probability cutoff : %s' % prob)


# display PyMOL session with identified conserved waters, showing H-bonds with other conserved waters, ligands or protein.
def displayInPyMOL(outdir, selectedPDBChain, atomNumbersProbDic):
    pdbCWMs = os.path.join(outdir, '%s_withConservedWaters.pdb' % selectedPDBChain)
    pdb = os.path.join(outdir, '%s.pdb' % selectedPDBChain)

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
    cmd.distance ('PW_HBA', '(cwm_protein and acc)','(cwm_waters and don)', 3.2)
    cmd.distance ('PW_HBD', '(cwm_protein and don)','(cwm_waters and acc)', 3.2)
    # h bonds between ligands and conserved waters
    cmd.distance ('LW_HBA', '(cwm_ligand and acc)','(cwm_waters and don)', 3.2)
    cmd.distance ('LW_HBD', '(cwm_ligand and don)','(cwm_waters and acc)', 3.2)
    # h bonds in between conserved waters
    cmd.distance ('HW_HBA', '(cwm_waters and acc)','(cwm_waters and don)', 3.2)
    cmd.distance ('HW_HBD', '(cwm_waters and don)','(cwm_waters and acc)', 3.2)

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
    cmd.create('all waters', 'resn hoh and %s' % selectedPDBChain)
    cmd.color('red','ss h and %s' % selectedPDBChain)
    cmd.color('yellow','ss s and %s' % selectedPDBChain)
    cmd.color('green','ss l+ and %s' % selectedPDBChain)
    cmd.show_as('cartoon', selectedPDBChain)
    cmd.set('ray_shadows', 0)


def okMobility(pdbFile, mobilityCutoff=2.0):
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
    logger.debug( 'Number of water moolecules is : %s' %nWaters )
    count = 0
    for line in reversed(pdbFileLines):
        if line.startswith('HETATM'):
            m = ((float(line[60:66])/avgB)/(float(line[54:60])/avgO))
            if m >= mobilityCutoff:
                count+=1
                pdbFileLines.remove(line)
    logger.info( 'water oxygen atoms having higher mobility are %s: '% count)
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

def okBfactor(pdbFile,normBCutoff=1.0):
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
            Bfactors.append(float(line[60:66]))
    avg = np.mean(Bfactors)
    stddev = np.sqrt(np.var(Bfactors))
    pdbFileLines = open(pdbFile).readlines()
    nWaters = len(pdbFileLines)-1
    logger.debug( 'Number of water moolecules is : %s' %nWaters )
    count = 0
    for line in reversed(pdbFileLines):
        if line.startswith('HETATM'):
            normB = ((float(line[60:66])-avg)/stddev)
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
        self.chain = chain.lower()
        self.pdb_id_folder = self.pdb_id[1:3]
        self.pdb_filename = self.pdb_id + '.pdb'
        self.water_coordinates = list()
        self.water_ids = list()
        self.waterIDCoordinates = {}

    def __repr__(self):
        return "%s_%s" % (self.pdb_id, self.chain)

    def calculate_water_coordinates(self, tmp_dir = False):
        path = os.path.join( tmp_dir, 'cwm_%s_Water.pdb' % self.__repr__() )
        logger.debug( 'making water coordinates dictcionary of cwm_%s_Water.pdb.' % self.__repr__())
        i = 1
        for line in open(path):
            line = line.strip()
            if line.startswith('HETATM'):
                key = self.__repr__()+'_'+str(int(line[22:30])) # water oxygen atom number
                self.waterIDCoordinates[key] = [line[30:38],line[38:46],line[46:54]]
                self.water_coordinates.append([line[30:38],line[38:46],line[46:54]])
                self.water_ids.append( key )
                i += 1
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
            accepts a '1234:B' formatted string and creates a protein object out of it
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
                raise IndexError, "The index (%d) is out of range." % key
            return self.proteins[key] #Get the data from elsewhere
        else:
            raise TypeError, "Invalid argument type."


def makePDBwithConservedWaters(ProteinsList, temp_dir, outdir):
    logger.info( 'Minimum desired degree of conservation is : %s' % ProteinsList.probability )
    cmd.delete('cwm_*')
    logger.info( 'loading all pdb chains ...' )
    for protein in ProteinsList:
        cmd.load(os.path.join(temp_dir, protein.pdb_filename),'cwm_%s' % protein.pdb_id)
        cmd.create('cwm_%s' % protein, 'cwm_%s & chain %s' % (protein.pdb_id, protein.chain))
        cmd.delete( 'cwm_%s' % protein.pdb_id )

    logger.info( 'Superimposing all pdb chains ...' )
    for protein in ProteinsList[1:]:
        logger.info( 'superimposing %s: ' % protein )
        cmd.super('cwm_%s' % protein, 'cwm_%s' % ProteinsList[0])
        cmd.orient( 'cwm_%s' % ProteinsList[0] )

    logger.info( 'Creating new pymol objects of only water molecules for each pdb chain...' )
    for protein in ProteinsList:
        cmd.create('cwm_%s_Water' % protein, 'cwm_%s & resname hoh' % protein)

    logger.info( 'saving water molecules and proteins in separate pdb files for each pdb chain...' )
    for protein in ProteinsList:
        cmd.save(os.path.join(temp_dir, 'cwm_%s.pdb' % protein), 'cwm_%s' % protein)
        cmd.save(os.path.join(temp_dir, 'cwm_%s_Water.pdb' % protein), 'cwm_%s_Water' % protein)

    cmd.delete('cwm_*')

    ### filter ProteinsList by mobility or normalized B factor cutoff

    logger.debug( 'proteins chains list is %s proteins long :' % len(ProteinsList.proteins) )
    length = len(ProteinsList.proteins)
    if ProteinsList.refinement == 'Mobility':
        logger.info( 'Filtering water oxygen atoms by Mobility' )
        for protein in reversed(ProteinsList.proteins):
            if not okMobility(os.path.join(temp_dir, 'cwm_%s_Water.pdb' % protein)):
                ProteinsList.proteins.remove(protein)

    if ProteinsList.refinement == 'Normalized B-factor': 
        logger.info( 'Filtering water oxygen atoms by Normalized B-factor' )
        for protein in reversed(ProteinsList.proteins):
            if not okBfactor(os.path.join(temp_dir, 'cwm_%s_Water.pdb' % protein)):
                ProteinsList.proteins.remove(protein)

    # make sure query structure is not filtered out
    queryStruct = ':'.join(str(ProteinsList.selectedPDBChain).upper().split('_'))
    if queryStruct not in ProteinsList.proteins:
        ProteinsList.add_protein_from_string(queryStruct)

    logger.debug( 'filtered proteins chains list is %s proteins long :' % len(ProteinsList.proteins) )

    """ 
        Filtered ProteinsList
    """

    selectedPDBChain = str(ProteinsList.selectedPDBChain)
    if len(ProteinsList.proteins) > 1:# Process further only if ProteinsList to use has more than one protein.
        water_coordinates = list()
        waterIDCoordinates = {}
        water_ids = list()
        for protein in ProteinsList:
            protein.calculate_water_coordinates( temp_dir )
            logger.debug( 'protein %s coordinates length is :%i' % (protein, len(protein.water_coordinates)))
            water_coordinates += protein.water_coordinates
            water_ids += protein.water_ids

        if water_coordinates:
            # Process further only if there are any water molecules list of similar protein structures.
            logger.info( 'number of water molecules to cluster : %i' % len(water_coordinates) )
            if len(water_coordinates) != 1:
                if len(water_coordinates) < 50000:
                    # Process further only if total number of water molecules to cluster is less than 50000.
                    cwm_count = 0
                    logger.info( 'clustering the water coordinates...' )
                    # returns a list of clusternumbers
                    # available optoins: single, complete, average, weighted, median centroid, wards
                    FD = hcluster.fclusterdata(water_coordinates, 
                            t=ProteinsList.inconsistency_coefficient, criterion='distance', 
                            metric='euclidean', depth=2, method='average')
                    FDlist = list(FD)
                    fcDic = {}
                    logger.info( 'making flat cluster dictionary...' )
                    for a,b in zip(water_ids,FDlist):
                        if fcDic.has_key(b):
                            fcDic[b].append(a)
                        else:
                            fcDic[b]=[a]

                    conservedWaterDic = {}
                    logger.info( 'extracting conserved waters from clusters...' )
                    for clusterNumber, waterMols in fcDic.items():
                        waterMolsNumber = len(waterMols)
                        uniquePDBs = set([a[:6] for a in waterMols])
                        if selectedPDBChain in uniquePDBs:
                            uniquePDBslen = len(set([a[:6] for a in waterMols]))
                            if uniquePDBslen == waterMolsNumber:
                                probability = float(uniquePDBslen) / len(ProteinsList)
                                logger.info( 'Degree of conservation is : %s' % probability )
                                if probability > ProteinsList.probability:
                                    logger.info('Here is conserved water molecule...')
                                    cwm_count += 1
                                    for waterMol in waterMols:
                                        if conservedWaterDic.has_key(waterMol[:6]):
                                            conservedWaterDic[waterMol[:6]].append('_'.join([waterMol[7:],str(probability)]))
                                        else:
                                            conservedWaterDic[waterMol[:6]] = ['_'.join([waterMol[7:],str(probability)])]
                                    #logger.debug( 'Updated conserved waters dictionary is : %s' % conservedWaterDic )
                            elif uniquePDBslen < waterMolsNumber:
                                logger.debug( 'Warning : cutoff distance is too large...' )

                    logger.debug( 'conservedWaterDic keys are: %s' % conservedWaterDic.keys() )
                    if selectedPDBChain in conservedWaterDic.keys():
                        # save pdb file of only conserved waters for selected pdb
                        atomNumbersProbDic = {}
                        atomNumbers_Prob = conservedWaterDic[selectedPDBChain]
                        logger.info( """Degree of conservation for each conserved water molecule in cwm_%s_withConservedWaters.pdb ['atomNumber_DegreeOfConservation']: %s""" % ( selectedPDBChain, atomNumbers_Prob) )
                        for a in atomNumbers_Prob:
                            atomNumbersProbDic[a.split('_')[0]]=float(a.split('_')[1])
                        atomNumbers = atomNumbersProbDic.keys()
                        selectedPDBChainConservedWatersOut = open(os.path.join(temp_dir, 'cwm_'+selectedPDBChain+'_ConservedWatersOnly.pdb'),'w+')
                        selectedPDBChainIn = open(os.path.join(temp_dir, 'cwm_'+selectedPDBChain+'_Water.pdb'))
                        for line in selectedPDBChainIn:
                            if line.startswith('HETATM'):
                                if str(int(line[22:30])) in atomNumbers: # 
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
                        shutil.copy( os.path.join(temp_dir, 'cwm_%s_withConservedWaters.pdb' % selectedPDBChain), outdir)
                        shutil.copy(os.path.join(temp_dir, 'cwm_%s.pdb' % selectedPDBChain),outdir)
                        if os.path.exists(os.path.join(outdir, 'cwm_%s_withConservedWaters.pdb' % selectedPDBChain)):
                            logger.info( "%s structure has %s conserved water molecules." % (selectedPDBChain,cwm_count))
                            displayInPyMOL(outdir, 'cwm_%s' % selectedPDBChain, atomNumbersProbDic)
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


# Check whether the PDB structure is determined by X-ray or not.
def isXray(pdb):
    expInfoAddress='http://pdb.org/pdb/rest/customReport?pdbids=%s&customReportColumns=experimentalTechnique&service=wsdisplay&format=xml&ssa=n' % (pdb)
    expInfoURL = urllib.urlopen(expInfoAddress)
    url_string = expInfoURL.read()
    expInfoXML = parseString(url_string)
    expMethod = str(expInfoXML.getElementsByTagName('dimStructure.experimentalTechnique')[0].childNodes[0].nodeValue)
    if expMethod == 'X-RAY DIFFRACTION':
        return True
    else:
        return False

# Check whether given chain id is valid for given PDB or not
def chainPresent(pdb,chain):
    chainInfoAddress='http://pdb.org/pdb/rest/customReport?pdbids=%s&customReportColumns=entityId&service=wsdisplay&format=xml&ssa=n' % pdb
    chainInfoURL = urllib.urlopen(chainInfoAddress)
    url_string = chainInfoURL.read()
    chainInfoXML = parseString(url_string)
    chains = [str(b.childNodes[0].nodeValue) for b in chainInfoXML.getElementsByTagName('dimEntity.chainId')]
    if chain in chains:
        return True
    else:
        return False

# Fetch sequence cluster data from RCSB PDB for query protein.
def fetchpdbChainsList(selectedStruture,seq_id):
    pdbChainsList = []
    seqClustAddress = 'http://pdb.org/pdb/rest/sequenceCluster?cluster=%s&structureId=%s' % (seq_id, selectedStruture) #http://pdb.org/pdb/rest/sequenceCluster?cluster=95&structureId=3qkl.A
    seqClustURL = urllib.urlopen(seqClustAddress)
    toursurl_string= seqClustURL.read()
    if toursurl_string.startswith('An error has occurred'):
        return pdbChainsList
    else:
        seqCluster = parseString( toursurl_string )
        for xmlTag in seqCluster.getElementsByTagName('pdbChain'):
            pdbChain = str(xmlTag.getAttribute('name')).replace('.', ':')
            pdb = pdbChain.split(':')[0]
            if isXray(pdb):
                pdbChainsList.append(pdbChain)
                logger.info('%s' % pdbChain)
        return pdbChainsList


# Filter the list of PDB structures by given resolution cutoff
def filterbyResolution(pdbChainsList,resolutionCutoff):
    pdbsList = []
    for pdbChain in pdbChainsList:
        pdbsList.append(pdbChain.split(':')[0])
    pdbsList =list(set(pdbsList))

    filteredpdbChainsList = []
    pdbsResolution = {}
    for pdb in pdbsList:
        getResolutionAddress ='http://pdb.org/pdb/rest/customReport?pdbids=%s&customReportColumns=resolution&service=wsfile&format=xml&ssa=n' % (pdb)
        pdbsResolution_string = urllib.urlopen(getResolutionAddress).read()
        pdbsResolutionXML = parseString(pdbsResolution_string)
        res = str(pdbsResolutionXML.getElementsByTagName('dimStructure.resolution')[0].childNodes[0].nodeValue)
        pdbsResolution[pdb] = res
        logger.info('Resolution of pdb %s is : %s' % (pdb, res))
    logger.info( 'PDB chains with their resolution : %s' %pdbsResolution )

    for pdbChain in pdbChainsList:
        if pdbsResolution[pdbChain.split(':')[0]] != 'null':
            if float(pdbsResolution[pdbChain.split(':')[0]]) <= resolutionCutoff:
                filteredpdbChainsList.append(pdbChain)

    return filteredpdbChainsList


# The main function, which run step by step events to identify conserved water molecules in given protein structure.
def FindConservedWaters(selectedStruturePDB,selectedStrutureChain,seq_id,resolution,refinement,inconsistency_coefficient,prob):# e.g: selectedStruturePDB='3qkl',selectedStrutureChain='A'
    try:
        response=urllib.urlopen('http://74.125.228.100')
    except:
        logger.error('The PDB webserver is not reachable.')
        return None
    if not re.compile('^[a-z0-9]{4}$').match(selectedStruturePDB):
        logger.error( 'The entered PDB id is not valid.' )
        tkMessageBox.showinfo(title = 'Error message', 
            message = """The entered PDB id is not valid.""")
        return None
    if not isXray(selectedStruturePDB):
        logger.error( 'The entered PDB structure is not determined by X-ray crystallography.' )
        tkMessageBox.showinfo(title = 'Error message', 
            message = """The entered PDB structure is not determined by X-ray crystallography.""")
        return None
    if not re.compile('^[A-Z0-9]{1}$').match(selectedStrutureChain):
        logger.error( 'The entered PDB chain id is not valid.' )
        tkMessageBox.showinfo(title = 'Error message', 
            message = """The entered PDB chain id is not valid.""")
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
    if inconsistency_coefficient > 2.4:
        logger.info( 'The maximum allowed inconsistency coefficient threshold is 2.4 A' )
        tkMessageBox.showinfo(title = 'Error message', 
            message = """The maximum allowed inconsistency coefficient threshold is 2.4 A.""")
        return None
    if prob > 1.0 or prob < 0.4:
        logger.info( 'The degree of conservation is allowed from 0.4 A to 1.0 A.' )
        tkMessageBox.showinfo(title = 'Error message', 
            message = """The degree of conservation is allowed from 0.4 A to 1.0 A.""")
        return None
    online_pdb_db = 'http://www.pdb.org/pdb/files/%s.pdb'
    displayInputs(selectedStruturePDB,selectedStrutureChain,seq_id,resolution,inconsistency_coefficient,prob)

    tmp_dir = tempfile.mkdtemp()

    selectedStruture = ".".join([selectedStruturePDB.lower(),selectedStrutureChain.upper()]) # 3qkl.A
    up = ProteinsList(ProteinName = selectedStruture) # ProteinsList class instance up
    up.refinement = refinement
    up.probability = prob
    up.inconsistency_coefficient = inconsistency_coefficient
    logger.info( 'selectedStruture is : %s' % selectedStruture )
    up.selectedPDBChain = Protein(selectedStruturePDB, selectedStrutureChain) # up.selectedPDBChain = 3qkl_a
    logger.info( 'up selectedPDBChain is : %s' % up.selectedPDBChain )
    selectedPDBChain = str(up.selectedPDBChain)
    logger.info( 'selectedPDBChain name is : %s' % selectedPDBChain )
    logger.info( """Fetching protein chains list from PDB clusters ...
    This cluater contains: """ )
    pdbChainsList = fetchpdbChainsList(selectedStruture,seq_id) # ['3QKL:A', '4EKL:A', '3QKM:A', '3QKK:A', '3OW4:A', '3OW4:B', '3OCB:A', '3OCB:B', '4EKK:A', '4EKK:B']
    logger.info( 'Protein chains list contains %i pdb chains : %s' % (len(pdbChainsList), pdbChainsList))
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
    logger.info( 'Filtered protein chains list contains %i pdb chains. : %s' % (len(pdbChainsList), pdbChainsList) )
    for pdbChain in pdbChainsList:
        up.add_protein_from_string(pdbChain)
#    logger.debug( 'up is : %s' % up.proteins ) #[3qkl_a, 4ekl_a, 3qkm_a, 3qkk_a, 3ow4_a, 3ow4_b, 3ocb_a, 3ocb_b, 4ekk_a, 4ekk_b]
    if len(up.proteins)>1:
#        logger.debug( 'length of protein chains list is : %s' % len(up.proteins) )
        for protein in up:
            logger.debug( protein )
            logger.debug( protein.pdb_id )
            if not os.path.exists(os.path.join(tmp_dir, '%s.pdb' % protein.pdb_id)):
                logger.info( 'retrieving pdb from website : %s' % protein.pdb_id)
                urllib.urlretrieve(online_pdb_db % protein.pdb_id.upper(), os.path.join(tmp_dir, protein.pdb_id+'.pdb'))
        logger.info( 'making pdb with conserved waters...' )
        makePDBwithConservedWaters(up, tmp_dir, outdir)
    else:
        logger.info( "%s has only one PDB structure. We need atleast 2 structures to superimpose." % selectedPDBChain)
    shutil.rmtree(tmp_dir)
    logger.info("""PDB file of query protein with conserved waters "cwm_%s_withConservedWaters.pdb" and 
log file "pycwms.log" are saved in %s""" % ( selectedPDBChain, os.path.abspath(outdir)))



# Makes plugin GUI
class ConservedWaters(Frame):
    def __init__(self,parent):
        Frame.__init__(self, parent, background="white")
        self.parent=parent
        self.parent.title("PyCWMs - Find Conserved Waters")
        self.grid()
        self.makeWindow()

    def makeWindow(self):
        frame1 = Frame(self.parent)
        frame1.grid()

        Label(frame1, text="PDB id").grid(row=0, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=pdb_id_help).grid(row=0, column=2, sticky=W)
        v1 = StringVar(master=frame1)
        v1.set('')
        Entry(frame1,textvariable=v1).grid(row=0, column=1, sticky=W)

        Label(frame1, text="Chain id").grid(row=1, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=chain_help).grid(row=1, column=2, sticky=W)
        v2 = StringVar(master=frame1)
        v2.set('')
        Entry(frame1,textvariable=v2).grid(row=1, column=1, sticky=W)

        Label(frame1, text="Sequence identity cutoff").grid(row=2, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=seq_id_help).grid(row=2, column=2, sticky=W)
        v3 = StringVar(master=frame1)
        v3.set("95")
        OptionMenu(frame1, v3, '30', '40', '50', '70', '90', '95', '100').grid(row=2, column=1, sticky=W)

        Label(frame1, text="Structure resolution cutoff").grid(row=3, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=resolution_help).grid(row=3, column=2, sticky=W)
        v4 = StringVar(master=frame1)
        v4.set("2.0")
        Entry(frame1,textvariable=v4).grid(row=3, column=1, sticky=W)

        Label(frame1, text="Refinement assessing method").grid(row=4, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=refinement_quality_help).grid(row=4, column=2, sticky=W)
        v5 = StringVar(master=frame1)
        v5.set('Mobility')
        OptionMenu(frame1, v5, 'Mobility', 'Normalized B-factor').grid(row=4, column=1, sticky=W)

        Label(frame1, text="Inconsistency coefficient threshold").grid(row=5, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=inconsistency_coefficient_help).grid(row=5, column=2, sticky=W)
        v6 = StringVar(master=frame1)
        v6.set("2.0")
        Entry(frame1,textvariable=v6).grid(row=5, column=1, sticky=W)

        Label(frame1, text="Degree of conservation").grid(row=6, column=0, sticky=W)
        Button(frame1,text=" Help  ",command=prob_help).grid(row=6, column=2, sticky=W)
        v7 = StringVar(master=frame1)
        v7.set("0.7")
        Entry(frame1,textvariable=v7).grid(row=6, column=1, sticky=W)

        frame2 = Frame(self.parent)
        frame2.grid()

        Button(frame2,text=" Find Conserved Water Molecules ",
            command = lambda: FindConservedWaters(str(v1.get()).lower(),str(v2.get()).upper(),str(v3.get()),float(v4.get()),str(v5.get()),float(v6.get()),float(v7.get()))).grid(row=0, column=1, sticky=W)

def main():
    root = Tk()
    app = ConservedWaters(root)
    root.mainloop()  

if __name__ == '__main__':
    main()


# Convert data types of input parameters given by command line.
def toPyCWMs(v1,v2,v3='95',v4=2.0,v5='Mobility',v6=2.0,v7=0.7):
    selectedStruturePDB = str(v1).lower()
    selectedStrutureChain = str(v2).upper()
    seq_id = str(v3)
    resolution = float(v4)
    refinement = str(v5)
    inconsistency_coefficient = float(v6)
    prob = float(v7)
    FindConservedWaters(selectedStruturePDB,selectedStrutureChain,seq_id,resolution,refinement,inconsistency_coefficient,prob)

#Extends PyMOL API to use this tool from command line.
cmd.extend('pycwms', toPyCWMs)


