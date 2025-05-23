__all__ = ['conduct_odme']


def conduct_odme(ui, odme_update_num, dp_id=0):
    """ calibrate traffic assignment results using traffic observations

    Parameters
    ----------
    ui
        network object generated by pg.read_network()

    odme_update_num
        number of iterations to be performed on ODME

    dp_id
        The sequence number of demand period listed in demand_periods in
        settings.yml. Its default value is 0.

        The current implementation of ODME only supports one demand period.

    Returns
    -------
    None

    Note
    ----
    You will need to call output_columns() and output_link_performance() to
    get the calibrated assignment results (i.e., paths/columns) in
    route_assignment.csv and link volumes (and other link attributes) in
    link_performance.csv.
    """
    print('conduct origin-destination demand matrix estimation (ODME)')

    # base assignment
    A = ui._base_assignment
    # check whether dp_id (demand period id) exists or not
    # exception will be thrown if dp_id does not exist
    A.get_demand_period_str(dp_id)
    # set up SPNetwork
    A.setup_spnetwork()

    # some constants
    delta = 0.05
    step_size = 0.01

    # the current implementation of ODME only supports one demand period
    column_pool = {k: v for k, v in A.get_column_pool().items() if k[1] == dp_id}
    links = A.get_links()
    zones = A.network.zones

    for j in range(odme_update_num):
        _update_link_volume(column_pool, links, zones, dp_id, j)

        # k = (at, dp, oz, dz)
        for k, cv in column_pool.items():
            if cv.is_route_fixed():
                continue

            for col in cv.get_columns():
                vol = col.get_volume()
                if not vol:
                    continue

                path_gradient_cost = 0

                orig_zone = zones[k[2]]
                if orig_zone.prod_obs > 0:
                    if not orig_zone.is_prod_obs_upper_bounded:
                        path_gradient_cost += orig_zone.prod_est_dev
                    elif orig_zone.is_prod_obs_upper_bounded and orig_zone.prod_est_dev > 0:
                        path_gradient_cost += orig_zone.prod_est_dev

                dest_zone = zones[k[3]]
                if dest_zone.attr_obs > 0:
                    if not dest_zone.is_attr_obs_upper_bounded:
                        path_gradient_cost += dest_zone.attr_est_dev
                    elif dest_zone.is_attr_obs_upper_bounded and dest_zone.attr_est_dev > 0:
                        path_gradient_cost += dest_zone.attr_est_dev

                for i in col.links:
                    link = links[i]
                    if link.obs >= 1:
                        if not link.is_obs_upper_bounded:
                            path_gradient_cost += link.est_dev
                        elif link.is_obs_upper_bounded and link.est_dev > 0:
                            path_gradient_cost += link.est_dev

                col.set_gradient_cost(path_gradient_cost)

                change_vol_ub = vol * delta
                change_vol_lb = -change_vol_ub

                change_vol = step_size * path_gradient_cost
                if change_vol < change_vol_lb:
                    change_vol = change_vol_lb
                elif change_vol > change_vol_ub:
                    change_vol = change_vol_ub

                col.set_volume(max(1, vol - change_vol))


def _update_link_volume(column_pool, links, zones, dp_id, iter_num):
    # reset the volume for each link
    for link in links:
        if not link.length:
            break

        link.reset_period_flow_vol()

    # reset the estimated attraction and production
    for z in zones.values():
        z.attr_est = 0
        z.prod_est = 0

    # update estimations and link volume
    # k = (at, dp, oz, dz)
    for k, cv in column_pool.items():
        for col in cv.get_columns():
            vol = col.get_volume()
            if not vol:
                continue

            zones[k[2]].prod_est += vol
            zones[k[3]].attr_est += vol

            for i in col.links:
                # to be consistent with _update_link_and_column_volume()
                # pce_ratio = 1 and vol * pce_ratio
                links[i].increase_period_flow_vol(dp_id, vol)

    # ODME statistics
    total_abs_gap = 0
    total_attr_gap = 0
    total_prod_gap = 0
    total_link_gap = 0

    # calculate estimation deviation for each link
    for link in links:
        if not link.length:
            break

        link.calculate_td_vdf()

        if link.obs < 1:
            continue

        # problematic: est_dev is a scalar rather than a vector?
        # code optimization: wrap it as a member function for class Link
        link.est_dev = link.get_period_flow_vol(dp_id) - link.obs
        total_abs_gap += abs(link.est_dev)
        total_link_gap += link.est_dev / link.obs

    # calculate estimation deviations for each zone
    for z in zones.values():
        if z.attr_obs >= 1:
            dev = z.attr_est - z.attr_obs
            z.attr_est_dev = dev

            total_abs_gap += abs(dev)
            total_attr_gap += dev / z.attr_obs

        if z.prod_obs >= 1:
            dev = z.prod_est - z.prod_obs
            z.prod_est_dev = dev

            total_abs_gap += abs(dev)
            total_prod_gap += dev / z.prod_obs

    print(f'current iteration number in ODME: {iter_num}\n'
          f'total absolute estimation gap: {total_abs_gap:,.2f}\n'
          f'total relative estimation gap (link): {total_link_gap:.2%}\n'
          f'total relative estimation gap (zone attraction): {total_attr_gap:.2%}\n'
          f'total relative estimation gap (zone production): {total_prod_gap:.2%}\n')