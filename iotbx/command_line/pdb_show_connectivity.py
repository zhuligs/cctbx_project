# LIBTBX_SET_DISPATCHER_NAME iotbx.pdb.show_connectivity

from __future__ import division
from libtbx.utils import Sorry, Usage
import sys

master_phil = """
pdb_file = None
  .type = path
selection = None
  .type = atom_selection
"""

def run (args, out=sys.stdout) :
  def show_usage() :
    raise Usage("""\
iotbx.pdb.show_connectivity model.pdb

Extracts the bondes specified by CONECT records and displays the atom IDs.""")
  if (len(args) == 0) : show_usage()
  import iotbx.pdb.hierarchy
  import iotbx.phil
  from scitbx.array_family import flex
  pdb_inp = None
  cmdline = iotbx.phil.process_command_line_with_files(
    args=args,
    master_phil_string=master_phil,
    pdb_file_def="pdb_file")
  params = cmdline.work.extract()
  if (params.pdb_file is None) :
    show_usage()
  pdb_inp = iotbx.pdb.hierarchy.input(file_name=params.pdb_file)
  if (len(pdb_inp.input.atoms()) == 0) :
    raise Sorry("'%s' is not a PDB file or does not contain any atoms." %
      params.pdb_file)
  elif (type(pdb_inp.input).__name__ == 'cif_input') :
    raise Sorry("Only PDB-format files are supported - mmCIF format does "+
      "not contain the necessary records.")
  bonds = pdb_inp.input.extract_connectivity()
  if (bonds is None) :
    raise Sorry("No CONECT records found in PDB file.")
  atoms = pdb_inp.hierarchy.atoms()
  selection = flex.bool(len(atoms), True)
  if (params.selection is not None) :
    selection = pdb_inp.hierarchy.atom_selection_cache().selection(
      params.selection)
  n_bonded = 0
  for i_seq, bonded in enumerate(bonds) :
    if (not selection[i_seq]) : continue
    if (len(bonded) > 0) :
      n_bonded += 1
      print >> out, "%s:" % atoms[i_seq].id_str()
      for j_seq in bonded :
        print >> out, "  %s" % atoms[j_seq].id_str()
  if (n_bonded == 0) :
    raise Sorry("No atoms with CONECT records found in selection.")

if (__name__ == "__main__") :
  run(sys.argv[1:])
