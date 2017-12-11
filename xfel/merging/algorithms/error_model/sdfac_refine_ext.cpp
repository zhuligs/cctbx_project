#include <boost/python/module.hpp>
#include <boost/python/def.hpp>
#include <dials/array_family/reflection_table.h>

namespace xfel {
namespace merging {
namespace error_model {
namespace sdfac_refine {

typedef
 scitbx::af::versa<cctbx::miller::index<>, scitbx::af::flex_grid<> > shared_miller;

using namespace dials::af;

static scitbx::af::shared<double>
compute_normalized_deviations(reflection_table ISIGI, shared_miller hkl_list) {
  /*
   * This formulation of the normalized deviations of a set of intensities and sigmas is similar to that
   * described in Evans 2011, but includes the nn term as currently implmented by aimless
   *
   */
  using namespace boost::python;
  scitbx::af::shared<double>         result(ISIGI.size(), 0);
  scitbx::af::shared<bool>           accepted(ISIGI.size(), false);
  scitbx::af::shared<double>         sigmas(ISIGI.size(), 0);

  scitbx::af::shared<double>         isum(hkl_list.size(), 0);
  scitbx::af::shared<double>         n_accept(hkl_list.size(), 0);

  scitbx::af::const_ref<double>      scaled_intensity = ISIGI["scaled_intensity"];
  scitbx::af::const_ref<double>      isigi = ISIGI["isigi"];
  scitbx::af::const_ref<std::size_t> miller_id = ISIGI["miller_id"];

  for (std::size_t i = 0; i < ISIGI.size(); i++) {
    // scaled intensity (iobs/slope)
    // corrected sigma (original sigma/slope)
    accepted[i] = isigi[i] != 0;
    if (isigi[i] == 0)
      continue;

    sigmas[i] = scaled_intensity[i] / isigi[i];
    accepted[i] = sigmas[i] > 0;
    if (sigmas[i] <= 0)
      continue;

    isum[miller_id[i]] += scaled_intensity[i];
    n_accept[miller_id[i]]++;
  }

  scitbx::af::shared<double> nn(hkl_list.size(), 0);
  for (std::size_t i = 0; i < hkl_list.size(); i++) {
    if (n_accept[i] > 0) {
      nn[i] = std::sqrt((n_accept[i]-1.0)/n_accept[i]);
    }
  }

  for (std::size_t i = 0; i < ISIGI.size(); i++) {
    if (!accepted[i]) continue;

    std::size_t n = n_accept[miller_id[i]];
    double meanIprime = (isum[miller_id[i]]-scaled_intensity[i]) / (n>1 ? (n-1) : 1);
    result[i] = nn[miller_id[i]] * (scaled_intensity[i] - meanIprime) / sigmas[i];
  }
  return result;
}

void
apply_sd_error_params(reflection_table ISIGI, const double sdfac, const double sdb, const double sdadd) {
  /*
   * Apply a set of sd params (sdfac, sdb and sdd) to an ISIGI reflection table
   */
  scitbx::af::const_ref<double> scaled_intensity = ISIGI["scaled_intensity"];
  scitbx::af::ref<double> isigi = ISIGI["isigi"];
  scitbx::af::shared<double> sigmas(ISIGI.size(), 0);
  scitbx::af::const_ref<std::size_t> miller_id = ISIGI["miller_id"];
  scitbx::af::const_ref<std::size_t> n_refl = ISIGI["n_refl"];
  scitbx::af::shared<double> isum; // can't get af::max to work...

  for (std::size_t i = 0; i < ISIGI.size(); i++) {
    // scaled intensity (iobs/slope)
    // corrected sigma (original sigma/slope)
    sigmas[i] = scaled_intensity[i] / isigi[i];

    while ((int)isum.size()-1 < (int)miller_id[i])
      isum.push_back(0);

    isum[miller_id[i]] += scaled_intensity[i];
  }

  for (std::size_t i = 0; i < ISIGI.size(); i++) {
    // compute meanIprime, which for each observation, is the mean of all other observations of this hkl
    double meanIprime = (isum[miller_id[i]]-scaled_intensity[i]) / (n_refl[i]>1 ? (n_refl[i]-1) : 1);

    // apply correction parameters
    double tmp = std::pow(sigmas[i],2) + sdb * meanIprime + std::pow(sdadd*meanIprime,2);

    // avoid rare negatives
    double minimum = 0.1 * std::pow(sigmas[i],2);
    if (tmp < minimum)
      tmp = minimum;

    double sigma_corrected = sdfac * std::sqrt(tmp);
    SCITBX_ASSERT(sigma_corrected != 0.0);
    isigi[i] = scaled_intensity[i] / sigma_corrected;
  }
}

namespace boost_python { namespace {
  void
  init_module() {
    using namespace boost::python;
    def("compute_normalized_deviations", &compute_normalized_deviations);
    def("apply_sd_error_params", &apply_sd_error_params);
}
}}
}}}} // namespace

BOOST_PYTHON_MODULE(xfel_sdfac_refine_ext)
{
  xfel::merging::error_model::sdfac_refine::boost_python::init_module();

}