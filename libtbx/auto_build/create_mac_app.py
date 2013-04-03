
# XXX this module is designed to be run independently of the rest of CCTBX if
# necessary, although it will use installed resources if found

from __future__ import division
try :
  import libtbx.load_env
except ImportError, e :
  libtbx_env = None
else :
  libtbx_env = libtbx.env
import argparse
import shutil
import re
import os
import sys

def run (args, out=sys.stdout) :
  if (sys.platform != "darwin") :
    print >> out, "This application will only run on Mac systems."
    return 1
  parser = argparse.ArgumentParser(
    description="Utility for creating an iconified Mac launcher for the specified command, which must be present in $LIBTBX_BUILD/bin.")
  bin_path = icns_path = None
  if (libtbx_env is not None) :
    bin_path = os.path.join(abs(libtbx_env.build_path), "bin")
    icns_path = libtbx_env.find_in_repositories(
      relative_path="gui_resources/icons/custom/phenix.icns",
      test=os.path.exists)
  parser.add_argument("--bin_dir", dest="bin_dir", action="store",
    help="Directory containing target executable.", default=bin_path)
  parser.add_argument("--app_name", dest="app_name", action="store",
    help="Name of iconified program", default=None)
  parser.add_argument("--icon", dest="icon", action="store",
    help="Path to .icns file", default=icns_path)
  parser.add_argument("--dest", dest="dest", action="store",
    help="Destination path", default=os.getcwd())
  options, args = parser.parse_known_args(args)
  if (len(args) == 0) :
    return parser.error("Executable name not specified.")
  if (options.bin_dir is None) :
    return parser.error("Executables directory not specified.")
  program_name = args[-1]
  build_dir = abs(libtbx.env.build_path)
  bin_dir = os.path.join(build_dir, "bin")
  if (not program_name in os.listdir(bin_dir)) :
    print >> out, "No program named '%s' found in %s." % (program_name,
      bin_dir)
    return 1
  try :
    import py2app.script_py2applet
  except ImportError, e :
    print >> out, "py2app not installed."
    return 1
  app_name = program_name
  if (options.app_name is not None) :
    app_name = options.app_name
  if (os.path.isdir("py2app_tmp")) :
    shutil.rmtree("py2app_tmp")
  os.mkdir("py2app_tmp")
  os.chdir("py2app_tmp")
  f = open("%s.py" % app_name, "w")
  f.write("""
import os
import sys
os.environ["PYTHONPATH"] = ""
os.spawnv(os.P_NOWAIT, "%s", ["%s"])
""" % (os.path.join(bin_dir, program_name), app_name))
  f.close()
  f = open("setup.cfg", "w")
  f.write("""\
[py2app]
argv-emulation=0""")
  f.close()
  script_name = re.sub(".pyc$", ".py", py2app.script_py2applet.__file__)
  import subprocess
  executable = sys.executable
  if (libtbx_env is not None) :
    executable = abs(libtbx.env.python_exe)
  args = [executable, script_name, "--make-setup", "%s.py" % app_name]
  if (options.icon is not None) :
    args.append(options.icon)
  rc = subprocess.call(args)
  if (rc != 0) :
    return rc
  args = [executable, "setup.py", "py2app", "-A"]
  rc = subprocess.call(args)
  if (rc != 0) :
    return rc
  app_path = os.path.abspath(os.path.join("dist", "%s.app" % app_name))
  assert os.path.isdir(app_path), app_path
  os.chdir(options.dest)
  if (os.path.exists("%s.app" % app_name)) :
    shutil.rmtree("%s.app" % app_name)
  shutil.move(app_path, os.getcwd())
  print >> out, "Created %s" % os.path.join(os.getcwd(), "%s.app" % app_name)
  return 0

if (__name__ == "__main__") :
  sys.exit(run(sys.argv[1:]))
