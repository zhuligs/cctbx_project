#ifndef CCTBX_RESTRAINTS_PAIR_PROXIES_H
#define CCTBX_RESTRAINTS_PAIR_PROXIES_H

#include <cctbx/restraints/bond.h>
#include <cctbx/restraints/repulsion.h>
#include <cctbx/crystal/pair_tables.h>

namespace cctbx { namespace restraints {

  void
  add_pairs(
    crystal::pair_asu_table<>& pair_asu_table,
    af::const_ref<bond_simple_proxy> const& bond_simple_proxies)
  {
    for(unsigned i=0;i<bond_simple_proxies.size();i++) {
      pair_asu_table.add_pair(bond_simple_proxies[i].i_seqs);
    }
  }

  class pair_proxies
  {
    public:
      pair_proxies() {}

      pair_proxies(
        af::const_ref<bond_params_dict> const& bond_params_table,
        af::const_ref<std::string> const& repulsion_types,
        restraints::repulsion_distance_table const& repulsion_distance_table,
        restraints::repulsion_radius_table const& repulsion_radius_table,
        double repulsion_distance_default,
        std::vector<crystal::pair_asu_table<> > const& shell_asu_tables,
        af::const_ref<double> const& shell_distance_cutoffs,
        double nonbonded_distance_cutoff,
        double nonbonded_buffer,
        double vdw_1_4_factor)
      :
        n_unknown_repulsion_type_pairs(0)
      {
        CCTBX_ASSERT(repulsion_types.size() == bond_params_table.size());
        CCTBX_ASSERT(shell_asu_tables.size() > 0);
        CCTBX_ASSERT(shell_distance_cutoffs.size() == shell_asu_tables.size());
        for(unsigned i=0; i<shell_asu_tables.size(); i++) {
          CCTBX_ASSERT(shell_asu_tables[i].table().size()
                    == bond_params_table.size());
        }
        bond_proxies = bond_sorted_asu_proxies(
          shell_asu_tables[0].asu_mappings());
        repulsion_proxies = repulsion_sorted_asu_proxies(
          shell_asu_tables[0].asu_mappings());
        double distance_cutoff = std::max(
          af::max(shell_distance_cutoffs),
          nonbonded_distance_cutoff+nonbonded_buffer);
        bool minimal = false;
        crystal::neighbors::fast_pair_generator<> pair_generator(
          shell_asu_tables[0].asu_mappings(),
          distance_cutoff,
          minimal);
        double nonbonded_distance_cutoff_sq = nonbonded_distance_cutoff
                                            * nonbonded_distance_cutoff;
        while (!pair_generator.at_end()) {
          direct_space_asu::asu_mapping_index_pair_and_diff<>
            pair = pair_generator.next();
          if (shell_asu_tables[0].contains(pair)) {
            bond_proxies.process(
              make_bond_asu_proxy(bond_params_table, pair));
          }
          else if (shell_asu_tables.size() > 1
                   && shell_asu_tables[1].contains(pair)) {
            continue;
          }
          else if (shell_asu_tables.size() > 2
                   && shell_asu_tables[2].contains(pair)) {
            repulsion_proxies.process(make_repulsion_asu_proxy(
              repulsion_types,
              repulsion_distance_table,
              repulsion_radius_table,
              repulsion_distance_default,
              pair,
              vdw_1_4_factor));
          }
          else if (pair.dist_sq <= nonbonded_distance_cutoff_sq) {
            repulsion_proxies.process(make_repulsion_asu_proxy(
              repulsion_types,
              repulsion_distance_table,
              repulsion_radius_table,
              repulsion_distance_default,
              pair));
          }
        }
      }

      static
      bond_asu_proxy
      make_bond_asu_proxy(
        af::const_ref<bond_params_dict> const& bond_params_table,
        direct_space_asu::asu_mapping_index_pair const& pair)
      {
        unsigned i, j;
        if (pair.i_seq <= pair.j_seq) {
          i = pair.i_seq;
          j = pair.j_seq;
        }
        else {
          i = pair.j_seq;
          j = pair.i_seq;
        }
        bond_params_dict const& params_dict = bond_params_table[i];
        bond_params_dict::const_iterator params = params_dict.find(j);
        if (params == params_dict.end()) {
          throw error(
            "Unknown bond parameters (incomplete bond_params_table).");
        }
        return bond_asu_proxy(pair, params->second);
      }

      repulsion_asu_proxy
      make_repulsion_asu_proxy(
        af::const_ref<std::string> const& repulsion_types,
        restraints::repulsion_distance_table const& repulsion_distance_table,
        restraints::repulsion_radius_table const& repulsion_radius_table,
        double repulsion_distance_default,
        direct_space_asu::asu_mapping_index_pair const& pair,
        double vdw_factor=1)
      {
        std::string const& rep_type_i = repulsion_types[pair.i_seq];
        std::string const& rep_type_j = repulsion_types[pair.j_seq];
        repulsion_distance_table::const_iterator
          distance_dict = repulsion_distance_table.find(rep_type_i);
        if (distance_dict != repulsion_distance_table.end()) {
          repulsion_distance_dict::const_iterator
            dict_entry = distance_dict->second.find(rep_type_j);
          if (dict_entry != distance_dict->second.end()) {
            return repulsion_asu_proxy(pair, dict_entry->second*vdw_factor);
          }
        }
        distance_dict = repulsion_distance_table.find(rep_type_j);
        if (distance_dict != repulsion_distance_table.end()) {
          repulsion_distance_dict::const_iterator
            dict_entry = distance_dict->second.find(rep_type_i);
          if (dict_entry != distance_dict->second.end()) {
            return repulsion_asu_proxy(pair, dict_entry->second*vdw_factor);
          }
        }
        restraints::repulsion_radius_table::const_iterator
          radius_i = repulsion_radius_table.find(rep_type_i);
        if (radius_i != repulsion_radius_table.end()) {
          restraints::repulsion_radius_table::const_iterator
            radius_j = repulsion_radius_table.find(rep_type_j);
          if (radius_j != repulsion_radius_table.end()) {
            return repulsion_asu_proxy(
              pair, (radius_i->second+radius_j->second)*vdw_factor);
          }
        }
        if (repulsion_distance_default > 0) {
          n_unknown_repulsion_type_pairs++;
          return repulsion_asu_proxy(
            pair, repulsion_distance_default*vdw_factor);
        }
        throw error(
         "Unknown repulsion type pair (incomplete repulsion_distance_table): "
         + rep_type_i + " - " + rep_type_j);
      }

      bond_sorted_asu_proxies bond_proxies;
      repulsion_sorted_asu_proxies repulsion_proxies;
      unsigned n_unknown_repulsion_type_pairs;
  };

}} // namespace cctbx::restraints

#endif // CCTBX_RESTRAINTS_PAIR_PROXIES_H
