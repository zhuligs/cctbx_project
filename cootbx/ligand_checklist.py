
from __future__ import division
import time
import os
import sys

t_wait = 250

def start_coot_and_wait (
    pdb_file,
    map_file,
    ligand_files,
    ligand_ccs,
    work_dir=None,
    coot_cmd="coot",
    log=None) :
  from iotbx import file_reader
  from libtbx.str_utils import make_header
  from libtbx import easy_run
  assert (len(ligand_files) > 0) and (len(ligand_files) == len(ligand_ccs))
  if (log is None) : log = sys.stdout
  if (work_dir is None) : work_dir = os.getcwd()
  if (not os.path.isdir(work_dir)) :
    os.makedirs(work_dir)
  base_script = __file__.replace(".pyc", ".py")
  ligand_xyzs = []
  for pdb_file in ligand_files :
    pdb_in = file_reader.any_file(pdb_file, force_type="pdb")
    pdb_in.assert_file_type("pdb")
    coords = pdb_in.file_object.atoms().extract_xyz()
    ligand_xyzs.append(coords.mean())
  ligand_info = zip(ligand_files, ligand_ccs, ligand_xyzs)
  f = open("edit_in_coot.py", "w")
  f.write(open(base_script).read())
  f.write("\n")
  f.write("import coot\n")
  f.write("m = manager(%s)\n" % str(ligand_info))
  f.close()
  make_header("Ligand selection in Coot", log)
  rc = easy_run.call("\"%s\" --no-state-script --script edit_in_coot.py &" %
    coot_cmd)
  if (rc != 0) :
    raise RuntimeError("Launching Coot failed with status %d" % rc)
  print >> log, "  Waiting for user input at %s" % str(time.asctime())
  out_file = ".COOT_LIGANDS"
  while (True) :
    if (os.path.isfile(out_file)) :
      print >> log, "  Coot editing complete at %s" % str(time.asctime())
      selected_ligands = [ int(s) for s in open(out_file).read().split() ]
      if (len(selected_ligands) == 0) :
        return None
      elif (len(selected_ligands) == 1) :
        return ligand_files[selected_ligands[0]]
      else :
        combined_hierarchy = hierarchy.root()
        model = hierarchy.model()
        combined_hierarchy.append_model(model)
        ligand_chain = hierarchy.chain(id='X')
        model.append_chain(ligand_chain)
        # TODO check for ligand overlaps
        for k, i_lig in enumerate(selected_ligands) :
          ligand_in = file_reader.any_file(ligand_files[i_lig], force_type="pdb")
          lig_hierarchy = ligand_in.file_object.construct_hierarchy()
          residue = lig_hierarchy.only_model().only_chain().only_residue_group()
          residue.resseq = "%4d" % (k+1)
          ligand_chain.append_residue_group(residue.detached_copy())
        f = open("ligands_from_coot.pdb", "w")
        f.write(combined_hierarchy.as_pdb_string())
        f.close()
        return os.path.join(os.getcwd(), "ligands_from_coot.pdb")
    else :
      time.sleep(t_wait / 1000.)
  assert (False)

class manager (object) :
  def __init__ (self, ligand_file_info) :
    import gtk
    import coot # import dependency
    title = "Select ligand(s)"
    self.ligand_file_info = ligand_file_info
    self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    self.window.set_default_size(300, 200)
    self.window.set_title(title)
    scrolled_win = gtk.ScrolledWindow()
    outside_vbox = gtk.VBox(False, 2)
    inside_vbox = gtk.VBox(False, 0)
    inside_vbox.set_border_width(2)
    self.window.add(outside_vbox)
    outside_vbox.pack_start(scrolled_win, True, True, 0) # expand fill padding
    scrolled_win.add_with_viewport(inside_vbox)
    scrolled_win.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
    frame = gtk.Frame(title)
    vbox = gtk.VBox(False, 0)
    inside_vbox.pack_start(frame, False, False, 2)
    self.model = gtk.ListStore(bool, gobject.TYPE_STRING, gobject.TYPE_STRING)
    tv = gtk.TreeView(self.model)
    cell1 = gtk.CellRendererToggle()
    cell1.connect("toggled", self.OnToggle, self.model)
    col1 = gtk.TreeViewColumn("Keep")
    col1.pack_start(cell1, False)
    col1.add_attribute(cell1, "active", 0)
    cell2 = gtk.CellRendererText()
    col2 = gtk.TreeViewColumn("File")
    col2.pack_start(cell2, False)
    col2.add_attribute(cell2, "text", 1)
    cell3 = gtk.CellRendererText()
    col3 = gtk.TreeViewColumn("CC")
    col3.pack_start(cell3, False)
    col3.add_attribute(cell3, "text", 2)
    tv.append_column(col1)
    tv.append_column(col2)
    tv.append_column(col3)
    frame.add(tv)
    for file_name, cc, xyz in ligand_file_info :
      self.model.append([False, os.path.basename(file_name), cc])
    continue_btn = gtk.Button("Close and continue")
    continue_btn.connect("clicked", self.OnContinue)
    outside_vbox.pack_end(continue_btn, False, False, 0)
    self.window.show_all()

  def OnToggle (self, cell, path, model):
    model[path][0] = not model[path][0]

  def OnContinue (self, *args) :
    selected = []
    for i_lig in range(len(self.ligand_file_info)) :
      if (model[i_lig][0]) :
        print "  selected %d" % i_lig
        selected.append(i_lig)
    open(".COOT_LIGANDS", "W").write(" ".join(selected))
    dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO,
      gtk.BUTTONS_OK,
      "The selected ligands have been saved.  You may now close Coot.")
    dialog.run()
    dialog.destroy()
