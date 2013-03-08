from __future__ import division
import mmtbx.utils
import iotbx.phil
from scitbx.array_family import flex
from libtbx.utils import Sorry, date_and_time
from libtbx import adopt_init_args
from libtbx.str_utils import show_string
from libtbx.math_utils import ifloor, iceil
import libtbx.callbacks # import dependency
import os
import sys
import random
from mmtbx import map_tools
from cctbx import miller
from cctbx import maptbx

map_coeff_params_base_str = """\
  map_coefficients
    .multiple = True
    .short_caption = Map coefficients
    .style = auto_align
  {
    map_type = None
      .type = str
      .style = bold renderer:draw_map_type_widget
    format = *mtz phs
      .type = choice(multi=True)
    mtz_label_amplitudes = None
      .type = str
      .short_caption = MTZ label for amplitudes
      .style = bold
    mtz_label_phases = None
      .type = str
      .short_caption = MTZ label for phases
      .style = bold
    kicked = False
      .type = bool
      .short_caption = Kicked map
    fill_missing_f_obs = False
      .type = bool
      .short_caption = Fill missing F(obs) with F(calc)
    acentrics_scale = 2.0
      .type = float
      .help = Scale terms corresponding to acentric reflections (residual maps only: k==n)
      .expert_level = 2
    centrics_pre_scale = 1.0
      .type = float
      .help = Centric reflections, k!=n and k*n != 0: \
              max(k-centrics_pre_scale,0)*Fo-max(n-centrics_pre_scale,0)*Fc
      .expert_level = 2
    sharpening = False
      .type = bool
      .help = Apply B-factor sharpening
      .short_caption = Apply B-factor sharpening
      .style = bold
    sharpening_b_factor = None
      .type = float
      .help = Optional sharpening B-factor value
      .short_caption = Sharpening B-factor value (optional)
    exclude_free_r_reflections = False
      .type = bool
      .help = Exclude free-R selected reflections from output map coefficients
    isotropize = True
      .type = bool
    dev
      .expert_level=3
    {
      complete_set_up_to_d_min = False
        .type = bool
      aply_same_incompleteness_to_complete_set_at = randomly low high
        .type = choice(multi=False)
    }
    %s
  }
"""

ncs_average_param_str = """
ncs_average = False
  .type = bool
  .expert_level = 2
  .help = Perform NCS averaging on map using RESOLVE (without density \
      modification).  Will be ignored if NCS is not present.
  .short_caption = NCS average
"""

# for phenix.maps
map_coeff_params_str = map_coeff_params_base_str % ""
# for phenix.refine
map_coeff_params_ncs_str = map_coeff_params_base_str % ncs_average_param_str

map_params_base_str ="""\
  map
    .short_caption = XPLOR or CCP4 map
    .multiple = True
    .style = auto_align
  {
    map_type = None
      .type = str
      .expert_level=0
      .style = bold renderer:draw_map_type_widget
    format = xplor *ccp4
      .type = choice
      .short_caption = File format
      .caption = XPLOR CCP4
      .style = bold
    file_name = None
      .type = path
      .style = bold new_file
    kicked = False
      .type = bool
      .expert_level=0
    fill_missing_f_obs = False
      .type = bool
      .expert_level=0
    grid_resolution_factor = 1/4.
      .type = float
      .expert_level=0
    scale = *sigma volume
      .type = choice(multi=False)
      .expert_level=2
    region = *selection cell
      .type = choice
      .caption = Atom_selection Unit_cell
      .short_caption=Map region
    atom_selection = None
      .type = atom_selection
      .short_caption = Atom selection
    atom_selection_buffer = 3
      .type = float
    acentrics_scale = 2.0
      .type = float
      .help = Scale terms corresponding to acentric reflections (residual maps only: k==n)
      .expert_level=2
    centrics_pre_scale = 1.0
      .type = float
      .help = Centric reflections, k!=n and k*n != 0: \
              max(k-centrics_pre_scale,0)*Fo-max(n-centrics_pre_scale,0)*Fc
      .expert_level=2
    sharpening = False
      .type = bool
      .help = Apply B-factor sharpening
      .short_caption = Apply B-factor sharpening
      .style = bold
    sharpening_b_factor = None
      .type = float
      .help = Optional sharpening B-factor value
      .short_caption = Sharpening B-factor value (optional)
    exclude_free_r_reflections = False
      .type = bool
      .help = Exclude free-R selected reflections from map calculation
    isotropize = True
      .type = bool
    %s
  }
"""

map_params_str = map_params_base_str % ""
map_params_ncs_str = map_params_base_str % ncs_average_param_str

# XXX for phenix.maps
map_and_map_coeff_params_str = """\
%s
%s
"""%(map_coeff_params_str, map_params_str)

# XXX for phenix.refine
map_and_map_coeff_params_ncs_str = """\
%s
%s
"""%(map_coeff_params_ncs_str, map_params_ncs_str)


def map_and_map_coeff_master_params():
  return iotbx.phil.parse(map_and_map_coeff_params_str, process_includes=False)

maps_including_IO_params_str = """\
maps {
  input {
    pdb_file_name = None
      .type = path
      .optional = False
      .short_caption = Model file
      .style = bold file_type:pdb input_file
    reflection_data {
      %s
      r_free_flags {
        %s
      }
    }
  }
  output {
    directory = None
      .type = path
      .short_caption = Output directory
      .help = For GUI only.
      .style = bold output_dir noauto
    prefix = None
      .type = str
      .input_size = 100
      .short_caption = Output prefix
      .style = bold noauto
    title = None
      .type = str
      .short_caption = Job title
      .input_size = 400
      .style = noauto
    fmodel_data_file_format = mtz
      .optional=True
      .type=choice
      .help=Write Fobs, Fmodel, various scales and more to MTZ file
  }
  scattering_table = wk1995  it1992  *n_gaussian  neutron
    .type = choice
    .help = Choices of scattering table for structure factors calculations
  wavelength = None
    .type = float(value_min=0.2, value_max=10.)
    .input_size = 80
    .help = Optional X-ray wavelength (in Angstroms), which will be used to \
      set the appropriate anomalous scattering factors for the model.  This \
      will only affect the LLG map from Phaser.
  bulk_solvent_correction = True
    .type = bool
  anisotropic_scaling = True
    .type = bool
  skip_twin_detection = False
    .type = bool
    .short_caption = Skip automatic twinning detection
    .help = Skip automatic twinning detection
  omit {
    method = *simple
      .type = choice(multi=False)
    selection = None
      .type = str
      .short_caption = Omit selection
      .input_size = 400
  }
  %s
  %s
}
"""%(mmtbx.utils.data_and_flags_str_part1,
     mmtbx.utils.data_and_flags_str_part2,
     map_coeff_params_str,
     map_params_str)

# XXX for documentation
master_params = maps_including_IO_params_str

def maps_including_IO_master_params():
  return iotbx.phil.parse(maps_including_IO_params_str, process_includes=True)

def cast_map_coeff_params(map_type_obj):
  map_coeff_params_str = """\
    map_coefficients
    {
      format = *mtz phs
      mtz_label_amplitudes = %s
      mtz_label_phases = P%s
      map_type = %s
      kicked = %s
      fill_missing_f_obs = %s
    }
"""%(map_type_obj.format(), map_type_obj.format(), map_type_obj.format(),
     map_type_obj.kicked, map_type_obj.f_obs_filled)
  return iotbx.phil.parse(map_coeff_params_str, process_includes=False)

class map_coeffs_mtz_label_manager:

  def __init__(self, map_params):
    self._amplitudes = map_params.mtz_label_amplitudes
    self._phases = map_params.mtz_label_phases
    if(self._amplitudes is None): self._amplitudes = str(map_params.map_type)
    if(self._phases is None): self._phases = "PH"+str(map_params.map_type)

  def amplitudes(self):
    return self._amplitudes

  def phases(self, root_label, anomalous_sign=None):
    assert anomalous_sign is None or not anomalous_sign
    return self._phases

class write_xplor_map_file(object):

  def __init__(self, params, coeffs, atom_selection_manager=None,
               xray_structure=None):
    adopt_init_args(self, locals())
    fft_map = coeffs.fft_map(resolution_factor =
      self.params.grid_resolution_factor)
    if(self.params.scale == "volume"): fft_map.apply_volume_scaling()
    elif(self.params.scale == "sigma"): fft_map.apply_sigma_scaling()
    else: raise RuntimeError
    title_lines=["REMARK file: %s" %
      show_string(os.path.basename(self.params.file_name))]
    title_lines.append("REMARK directory: %s" %
      show_string(os.path.dirname(self.params.file_name)))
    title_lines.append("REMARK %s" % date_and_time())
    assert self.params.region in ["selection", "cell"]
    if(self.params.region == "selection" and xray_structure is not None) :
      map_iselection = None
      if atom_selection_manager is not None :
        map_iselection = self.atom_iselection()
      frac_min, frac_max = self.box_around_selection(
        iselection = map_iselection,
        buffer     = self.params.atom_selection_buffer)
      n_real = fft_map.n_real()
      gridding_first=[ifloor(f*n) for f,n in zip(frac_min,n_real)]
      gridding_last=[iceil(f*n) for f,n in zip(frac_max,n_real)]
      title_lines.append('REMARK map around selection')
      title_lines.append('REMARK   atom_selection=%s' %
        show_string(self.params.atom_selection))
      title_lines.append('REMARK   atom_selection_buffer=%.6g' %
        self.params.atom_selection_buffer)
      if(map_iselection is None):
        sel_size = self.xray_structure.scatterers().size()
      else:
        sel_size = map_iselection.size()
      title_lines.append('REMARK   number of atoms selected: %d' % sel_size)
    else:
      gridding_first = None
      gridding_last = None
      title_lines.append("REMARK map covering the unit cell")
    if params.format == "xplor" :
      fft_map.as_xplor_map(
        file_name      = self.params.file_name,
        title_lines    = title_lines,
        gridding_first = gridding_first,
        gridding_last  = gridding_last)
    else :
      fft_map.as_ccp4_map(
        file_name      = self.params.file_name,
        gridding_first = gridding_first,
        gridding_last  = gridding_last,
        labels=title_lines)

  def box_around_selection(self, iselection, buffer):
    sites_cart = self.xray_structure.sites_cart()
    if(iselection is not None):
      sites_cart = sites_cart.select(iselection)
    return self.xray_structure.unit_cell().box_frac_around_sites(
      sites_cart = sites_cart, buffer = buffer)

  def atom_iselection(self):
    if(self.params.region != "selection" or self.params.atom_selection is None):
      return None
    try:
      result = self.atom_selection_manager.selection(string =
        self.params.atom_selection).iselection()
    except KeyboardInterrupt: raise
    except Exception:
      raise Sorry('Invalid atom selection: %s' % self.params.atom_selection)
    if(result.size() == 0):
      raise Sorry('Empty atom selection: %s' % self.params.atom_selection)
    return result

def compute_f_calc(fmodel, params):
  from cctbx import miller
  coeffs_partial_set = fmodel.f_obs().structure_factors_from_scatterers(
    xray_structure = fmodel.xray_structure).f_calc()
  if(hasattr(params,"dev") and params.dev.complete_set_up_to_d_min):
    coeffs = fmodel.xray_structure.structure_factors(
      d_min = fmodel.f_obs().d_min()).f_calc()
    frac_inc = 1.*coeffs_partial_set.data().size()/coeffs.data().size()
    n_miss = coeffs.data().size() - coeffs_partial_set.data().size()
    if(params.dev.aply_same_incompleteness_to_complete_set_at == "randomly"):
      sel = flex.random_bool(coeffs.data().size(), frac_inc)
      coeffs = coeffs.select(sel)
    elif(params.dev.aply_same_incompleteness_to_complete_set_at == "low"):
      coeffs = coeffs.sort()
      coeffs = miller.set(
        crystal_symmetry = coeffs,
        indices = coeffs.indices()[n_miss+1:],
        anomalous_flag = coeffs.anomalous_flag()).array(
        data = coeffs.data()[n_miss+1:])
    elif(params.dev.aply_same_incompleteness_to_complete_set_at == "high"):
      coeffs = coeffs.sort(reverse=True)
      coeffs = miller.set(
        crystal_symmetry = coeffs,
        indices = coeffs.indices()[n_miss+1:],
        anomalous_flag = coeffs.anomalous_flag()).array(
        data = coeffs.data()[n_miss+1:])
  else:
    coeffs = coeffs_partial_set
  return coeffs

def map_coefficients_from_fmodel (fmodel,
    params,
    post_processing_callback=None,
    pdb_hierarchy=None):
  from mmtbx import map_tools
  import mmtbx
  from cctbx import miller
  mnm = mmtbx.map_names(map_name_string = params.map_type)
  if(mnm.k==0 and abs(mnm.n)==1):
    return compute_f_calc(fmodel, params)
  if (fmodel.is_twin_fmodel_manager()) and (mnm.phaser_sad_llg) :
    return None
  #XXXsave_k_part, save_b_part = None, None
  #XXXif(mnm.k is not None and abs(mnm.k) == abs(mnm.n) and fmodel.k_part()!=0):
  #XXX  save_k_part = fmodel.k_part()
  #XXX  save_b_part = fmodel.b_part()
  #XXX  fmodel.update_core(k_part=0, b_part=0)
  e_map_obj = fmodel.electron_density_map()
  coeffs = None
  if(not params.kicked):
    coeffs = e_map_obj.map_coefficients(
      map_type           = params.map_type,
      acentrics_scale    = params.acentrics_scale,
      centrics_pre_scale = params.centrics_pre_scale,
      fill_missing       = params.fill_missing_f_obs,
      isotropize         = params.isotropize,
      exclude_free_r_reflections=params.exclude_free_r_reflections,
      ncs_average=getattr(params, "ncs_average", False),
      post_processing_callback=post_processing_callback,
      pdb_hierarchy=pdb_hierarchy)
    if (coeffs is None) : return None
    if(coeffs.anomalous_flag()) :
      coeffs = coeffs.average_bijvoet_mates()
    if(params.sharpening):
      from mmtbx import map_tools
      coeffs, b_sharp = map_tools.sharp_map(
        sites_frac = fmodel.xray_structure.sites_frac(),
        map_coeffs = coeffs,
        b_sharp    = params.sharpening_b_factor)
  else:
    if (fmodel.is_twin_fmodel_manager()) :
      raise Sorry("Kicked maps are not supported when twinning is present.  "+
        "You can disable the automatic twin law detection by setting the "+
        "parameter maps.skip_twin_detection to True (or check the "+
        "corresponding box in the Phenix GUI).")
    if(params.map_type.count("anom")==0):
      coeffs = kick(
        fmodel   = e_map_obj.fmodel,
        map_type = params.map_type).map_coefficients
  # XXX need to figure out why this happens
  if (coeffs is None) :
    raise RuntimeError(("Map coefficient generation failed (map_type=%s, "
      "kicked=%s, sharpening=%s, isotropize=%s, anomalous=%s.") %
        (params.map_type, params.kicked, params.sharpening, params.isotropize,
         fmodel.f_obs().anomalous_flag()))
  # XXX is this redundant?
  if(coeffs.anomalous_flag()) :
    coeffs = coeffs.average_bijvoet_mates()
  #XXXif(mnm.k is not None and abs(mnm.k) == abs(mnm.n) and save_k_part is not None):
  #XXX  fmodel.update_core(k_part=save_k_part, b_part=save_b_part)
  return coeffs

def compute_xplor_maps(
    fmodel,
    params,
    atom_selection_manager=None,
    file_name_prefix=None,
    file_name_base=None,
    post_processing_callback=None) :
  assert ((post_processing_callback is None) or
          (hasattr(post_processing_callback, "__call__")))
  output_files = []
  for mp in params:
    if(mp.map_type is not None):
      coeffs = map_coefficients_from_fmodel(fmodel = fmodel, params = mp,
        post_processing_callback=post_processing_callback)
      if (coeffs is None) :
        raise Sorry("Couldn't generate map type '%s'." % mp.map_type)
      if(mp.file_name is None):
        output_file_name = ""
        if(file_name_prefix is not None): output_file_name = file_name_prefix
        if(file_name_base is not None):
          if(len(output_file_name)>0):
            output_file_name = output_file_name + "_"+file_name_base
          else: output_file_name = output_file_name + file_name_base
        if mp.format == "xplor" :
          ext = ".xplor"
        else :
          ext = ".ccp4"
        output_file_name = output_file_name + "_" + mp.map_type + "_map" + ext
        mp.file_name = output_file_name
      write_xplor_map_file(params = mp, coeffs = coeffs,
        atom_selection_manager = atom_selection_manager,
        xray_structure = fmodel.xray_structure)
      output_files.append(mp.file_name)
  return output_files

class compute_map_coefficients(object):

  def __init__(self,
               fmodel,
               params,
               mtz_dataset = None,
               post_processing_callback=None,
               pdb_hierarchy=None,
               log=sys.stdout):
    assert ((post_processing_callback is None) or
            (hasattr(post_processing_callback, "__call__")))
    self.mtz_dataset = mtz_dataset
    coeffs = None
    self.map_coeffs = []
    for mcp in params:
      if(mcp.map_type is not None):
        # XXX
        if(fmodel.is_twin_fmodel_manager()) and (mcp.isotropize) :
          mcp.isotropize = False
        coeffs = map_coefficients_from_fmodel(fmodel = fmodel,
          params = mcp,
          post_processing_callback = post_processing_callback,
          pdb_hierarchy = pdb_hierarchy)
        if("mtz" in mcp.format and coeffs is not None):
          lbl_mgr = map_coeffs_mtz_label_manager(map_params = mcp)
          if(self.mtz_dataset is None):
            self.mtz_dataset = coeffs.as_mtz_dataset(
              column_root_label = lbl_mgr.amplitudes(),
              label_decorator   = lbl_mgr)
          else:
            self.mtz_dataset.add_miller_array(
              miller_array      = coeffs,
              column_root_label = lbl_mgr.amplitudes(),
              label_decorator   = lbl_mgr)
          self.map_coeffs.append(coeffs)
        elif (coeffs is None) :
          if ((mcp.map_type == "anomalous") and
              (not fmodel.f_obs().anomalous_flag())) :
            # since anomalous map is included in the defaults, even if the
            # data are merged, no warning is issued here
            pass
          else :
            libtbx.warn(("Map coefficients not available for map type '%s'; "+
              "usually means you have requested an anomalous map but supplied "+
              "merged data, or indicates a twinning-related incompatibility.")%
              mcp.map_type)

  def write_mtz_file(self, file_name, mtz_history_buffer = None):
    from cctbx.array_family import flex
    if(self.mtz_dataset is not None):
      if(mtz_history_buffer is None):
        mtz_history_buffer = flex.std_string()
      mtz_history_buffer.append(date_and_time())
      mtz_history_buffer.append("> file name: %s" % os.path.basename(file_name))
      mtz_object = self.mtz_dataset.mtz_object()
      mtz_object.add_history(mtz_history_buffer)
      mtz_object.write(file_name = file_name)
      return True
    return False

class kick(object):

  def __init__(
      self,
      fmodel,
      crystal_gridding = None,
      map_type         = "2mFo-DFc",
      number_of_kicks  = 100,
      number_of_trials = 30):
    if(crystal_gridding is not None):
      crystal_gridding = fmodel.f_obs().crystal_gridding(
        d_min                   = fmodel.f_obs().d_min(),
        resolution_factor       = 0.25,
        grid_step               = None,
        symmetry_flags          = None,
        mandatory_factors       = None,
        max_prime               = 5,
        assert_shannon_sampling = True)
    fmodel_dc = fmodel.deep_copy()
    self.number_of_kicks = number_of_kicks
    assert self.number_of_kicks > 0
    map_coeffs = fmodel_dc.f_calc()
    complete_set = fmodel_dc.electron_density_map().map_coefficients(
      map_type = map_type, isotropize = True, fill_missing = True)
    def call_run_kick_loop(map_coeffs, small):
      map_coeff_data = self.run_kick_loop(map_coeffs = map_coeffs, small=small)
      return miller.set(
        crystal_symmetry = map_coeffs.crystal_symmetry(),
        indices          = map_coeffs.indices(),
        anomalous_flag   = False).array(data = map_coeff_data)
    map_data = None
    for it in xrange(number_of_trials):
      print it
      if(it<number_of_trials/2): small=False
      else: small=True
      if(it%2==0):
        map_coeffs_kick = call_run_kick_loop(map_coeffs=map_coeffs, small=small)
        fmodel_dc.update(
          f_calc       = map_coeffs_kick,
          r_free_flags = map_coeffs_kick.generate_r_free_flags())
        mc = fmodel_dc.electron_density_map().map_coefficients(
          map_type = map_type, isotropize = True, fill_missing = False)
        mc = mc.complete_with(complete_set)
      else:
        mc = call_run_kick_loop(map_coeffs=complete_set, small=small)
      #
      #sel = flex.random_bool(complete_set.indices().size(), 0.95)
      #mc=mc.select(sel)
      fft_map = miller.fft_map(
        crystal_gridding     = crystal_gridding,
        fourier_coefficients = mc)
      fft_map.apply_sigma_scaling()
      m = fft_map.real_map_unpadded()
      if(map_data is None): map_data = m
      else:
        for i in [0,0.1,0.2,0.3,0.4,0.5]:
          maptbx.intersection(
            map_data_1 = m,
            map_data_2 = map_data,
            threshold  = i)
        map_data= (m+map_data)/2
    for i in xrange(3):
      map_data = maptbx.node_interplation_averaging(map_coeffs.unit_cell(),
        map_data, 0.5)
    self.map_data = map_data
    self.map_coefficients = complete_set.structure_factors_from_map(
      map            = self.map_data,
      use_scale      = True,
      anomalous_flag = False,
      use_sg         = False)

  def run_kick_loop(self, map_coeffs, small):
    map_coeff_data = None
    for kick in xrange(self.number_of_kicks):
      print "  ", kick, small
      if(small):
        sel = flex.random_bool(map_coeffs.size(), random.choice([1,0.1,0.2,0.3]))
        ar = random.choice([0,0.01,0.02])
        pr = random.choice(list(xrange(5)))
      else:
        sel = ~flex.random_bool(map_coeffs.size(), random.choice([1,0.9,0.8,0.7]))
        if(random.choice([True, False])): sel = ~sel
        ar = random.choice([0,0.01,0.02,0.03,0.04,0.05])
        pr = random.choice(list(xrange(20)))
      mc = map_coeffs.randomize_amplitude_and_phase(
        amplitude_error=ar, phase_error_deg=pr, selection=sel)
      if(map_coeff_data is None): map_coeff_data = mc.data()
      else:                       map_coeff_data = map_coeff_data + mc.data()
    return map_coeff_data/self.number_of_kicks

#def averaged_phase_kicked_map(
#      fmodel,
#      map_type            = "2mFo-DFc",
#      phase_kick_fraction = 0.3,
#      number_of_kicks     = 100,
#      number_of_trials    = 10):
#  assert number_of_kicks > 0
#  complete_set = fmodel.electron_density_map().map_coefficients(
#    map_type = map_type, isotropize=True, fill_missing=True)
#  #
##  fft_map = complete_set.fft_map(resolution_factor=0.25)
##  fft_map.apply_sigma_scaling()
##  map_data_orig = fft_map.real_map_unpadded()
##  sites_frac = fmodel.xray_structure.sites_frac()
##  sites_cart = fmodel.xray_structure.sites_cart()
##  mv = 0
##  for sf in sites_frac:
##    mv += map_data_orig.eight_point_interpolation(sf)
##  mv /= sites_frac.size()
##  print mv
##
##
##  sel = maptbx.grid_indices_around_sites(
##                  unit_cell  = fmodel.xray_structure.unit_cell(),
##                  fft_n_real = map_data_orig.focus(),
##                  fft_m_real = map_data_orig.all(),
##                  sites_cart = sites_cart,
##                  site_radii = flex.double([1.0]*sites_cart.size()))
##  cutoff = flex.mean(map_data_orig.select(sel))
##  print cutoff
#  #
#  map_data = None
#  for it in xrange(number_of_trials):
#    print it
#    map_coeff_data = run_kick_loop(map_coeffs = complete_set,
#      number_of_kicks = number_of_kicks)
#    map_coeffs_ave_i = miller.set(
#      crystal_symmetry = complete_set.crystal_symmetry(),
#      indices          = complete_set.indices(),
#      anomalous_flag   = False).array(data = map_coeff_data)
#    fft_map = map_coeffs_ave_i.fft_map(resolution_factor=0.25)
#    fft_map.apply_sigma_scaling()
#    m = fft_map.real_map_unpadded()
#    if(map_data is None): map_data = m
#    else:
#      for i in [0,0.1,0.2,0.3,0.4,0.5]:
#        maptbx.intersection(
#          map_data_1 = m,
#          map_data_2 = map_data,
#          threshold  = i)#cutoff/3)#0.5)
#      map_data= (m+map_data)/2
#  #maptbx.kill_because_of_poor_neighbours(map_data, 0.5, 1)
#  #maptbx.convert_to_non_negative(map_data, 0)
#  return complete_set.structure_factors_from_map(
#    map            = map_data,
#    use_scale      = True,
#    anomalous_flag = False,
#    use_sg         = False)

class filter_by_averaged_phase_kicked_map(object):
  def __init__(self,
               fmodel,
               crystal_gridding,
               mean_positive_scale,
               map_type        = "2mFo-DFc",
               sigma_threshold = 0.5,
               fill_missing    = False):
    self.mc_original = map_tools.electron_density_map(
      fmodel = fmodel).map_coefficients(
        map_type = map_type,
        fill_missing = fill_missing)
    self.mc_kicked  = mmtbx.maps.kick(fmodel=fmodel,
      crystal_gridding=crystal_gridding).map_coefficients
    #
    maps = []
    for i, mc in enumerate([self.mc_original, self.mc_kicked]):
      fft_map = miller.fft_map(
        crystal_gridding     = crystal_gridding,
        fourier_coefficients = mc)
      fft_map.apply_sigma_scaling()
      m = fft_map.real_map_unpadded()
      maps.append(m)
    self.map_data_original, self.map_data_kicked = \
      maps[0].deep_copy(), maps[1].deep_copy()
    maptbx.intersection(
      map_data_1 = maps[0],
      map_data_2 = maps[1],
      threshold  = 0.5)
    self.map_data_original_filtered = maps[0]
    self.mc_original_filtered = fmodel.f_obs().structure_factors_from_map(
      map            = maps[0],
      use_scale      = True,
      anomalous_flag = False,
      use_sg         = False)
    self.mc_kicked_filtered = fmodel.f_obs().structure_factors_from_map(
      map            = maps[1],
      use_scale      = True,
      anomalous_flag = False,
      use_sg         = False)
    # compute best map

    obj = maptbx.local_scale(                                    # XXX HACK, but an option
      f_map               = self.mc_kicked,
      #map_data            = m,                                   # XXX HACK, but an option
      crystal_gridding    = crystal_gridding,                    # XXX HACK, but an option
      crystal_symmetry    = fmodel.f_obs().crystal_symmetry(),   # XXX HACK, but an option
      miller_array        = fmodel.f_obs(),                      # XXX HACK, but an option
      mean_positive_scale = mean_positive_scale)                 # XXX HACK, but an option
    self.mc5 = obj.map_coefficients                              # XXX HACK, but an option
    self.mc_original_filtered_local_scaled = self.mc5            # XXX HACK, but an option

#    obj1 = maptbx.local_scale(
#      map_data            = self.map_data_original.deep_copy(),
#      crystal_gridding    = crystal_gridding,
#      crystal_symmetry    = fmodel.f_obs().crystal_symmetry(),
#      miller_array        = fmodel.f_obs(),
#      mean_positive_scale = mean_positive_scale)
#    fft_map = miller.fft_map(
#        crystal_gridding     = crystal_gridding,
#        fourier_coefficients = obj1.map_coefficients)
#    fft_map.apply_sigma_scaling()
#    m1 = fft_map.real_map_unpadded()
#    self.tmp1 = obj1.map_coefficients
#    #
#    obj2 = maptbx.local_scale(
#      f_map               = self.mc_kicked,
#      crystal_gridding    = crystal_gridding,
#      crystal_symmetry    = fmodel.f_obs().crystal_symmetry(),
#      miller_array        = fmodel.f_obs(),
#      mean_positive_scale = mean_positive_scale)
#    fft_map = miller.fft_map(
#        crystal_gridding     = crystal_gridding,
#        fourier_coefficients = obj2.map_coefficients)
#    fft_map.apply_sigma_scaling()
#    m2 = fft_map.real_map_unpadded()
#    self.tmp2 = obj2.map_coefficients
#    #
#        #XXXo=maptbx.non_linear_map_modification_to_match_average_cumulative_histogram(
#        #XXX  map_1 = m1, map_2 = m2)
#        #XXXm1,m2 = o.map_1(), o.map_2()
#        #XXXself.tmp1 = obj1.map_coefficients.structure_factors_from_map(
#        #XXX  map            = m1,
#        #XXX  use_scale      = True,
#        #XXX  anomalous_flag = False,
#        #XXX  use_sg         = False)
#        #XXXself.tmp2 = obj1.map_coefficients.structure_factors_from_map(
#        #XXX  map            = m2,
#        #XXX  use_scale      = True,
#        #XXX  anomalous_flag = False,
#        #XXX  use_sg         = False)
#    #
#    for i in [0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0]:#,1.1,1.2,1.3,1.5,1.6,1.7,1.8,1.9,2.0]:
#      maptbx.intersection(
#        map_data_1 = m1,
#        map_data_2 = m2,
#        threshold  = i)
#    self.mc5 = obj1.map_coefficients.structure_factors_from_map(
#        map            = m2,
#        use_scale      = True,
#        anomalous_flag = False,
#        use_sg         = False)
#    self.mc_original_filtered_local_scaled = self.mc5


#    obj = maptbx.local_scale(
#      map_data            = self.map_data_original_filtered.deep_copy(),
#      crystal_gridding    = crystal_gridding,
#      crystal_symmetry    = fmodel.f_obs().crystal_symmetry(),
#      miller_array        = fmodel.f_obs(),
#      mean_positive_scale = mean_positive_scale)
#    self.mc_original_filtered_local_scaled = obj.map_coefficients
#    fft_map = miller.fft_map(
#        crystal_gridding     = crystal_gridding,
#        fourier_coefficients = self.mc_original_filtered_local_scaled)
#    fft_map.apply_sigma_scaling()
#    map_data_original_filtered_local_scaled = fft_map.real_map_unpadded()
#    maptbx.intersection(
#      map_data_1 = map_data_original_filtered_local_scaled,
#      map_data_2 = self.map_data_kicked,
#      threshold  = 0.5)
#    self.mc5 = fmodel.f_obs().complete_set(d_min=
#      fmodel.f_obs().d_min()-0.25).structure_factors_from_map(
#         map            = map_data_original_filtered_local_scaled,
#         use_scale      = True,
#         anomalous_flag = False,
#         use_sg         = False)
