from math import ceil


__all__ = ['perform_simple_simulation']


def perform_simple_simulation(ui, loading_profile='uniform'):
    """ perform simple traffic simulation using point queue model

    WARNING
    -------
    The underlying routing decision is made through find_path_for_agents(), which
    must be called before this function.

    Parameters
    ----------
    ui
        network object generated by pg.read_network()

    loading_profile
        demand loading profile, i.e., how agents are loaded to network with respect
        to their departure times. Three loading profiles are supported, which are
        uniform, random, and constant.

        With uniform loading profile, agents will be uniformly distributed between
        [simulation start time, simulation start time + simulation duration).

        With random loading profile, the departure time of each agent is randomly
        set up between [simulation start time, simulation start time + simulation duration).

        With constant loading profile, the departure times of all agents are the
        same, which are simulation start time.

    Returns
    -------
    None

    Note
    ----
    You will need to call output_agent_trajectory() to get the simulation
    results, i.e., trajectory of each agent (in trajectory.csv).
    """
    A = ui._base_assignment
    A.initialize_simulation(loading_profile)
    if not A.get_agents():
        return

    links = A.get_links()
    nodes = A.get_nodes()

    cum_arr = cum_dep = 0

    # number of simulation intervals in one minute (60s)
    num = A.cast_minute_to_interval(1)
    for i in range(A.get_total_simu_intervals()):
        if i % num == 0:
            print(f'simu time = {i/num} min, CA = {cum_arr}, CD = {cum_dep}')

        # comment out from now on as link.cum_arr and link.cum_dep are not used
        # for critical calculation
        # if i > 0:
        #     for link in links:
        #         link.cum_arr[i] = link.cum_arr[i-1]
        #         link.cum_dep[i] = link.cum_dep[i-1]

        if A.have_dep_agents(i):
            for a_no in A.get_td_agents(i):
                a = A.get_agent(a_no)
                if a.link_path is None:
                    continue

                # retrieve the first link given link path is in reverse order
                link_no = a.link_path[-1]
                link = links[link_no]
                # link.cum_arr[i] += 1
                link.entr_queue.append(a_no)
                cum_arr += 1

        for link in links:
            while link.entr_queue:
                a_no = link.entr_queue.popleft()
                agent = A.get_agent(a_no)
                link.exit_queue.append(a_no)
                intvl = A.cast_minute_to_interval(link.get_period_fftt(0))
                agent.update_dep_interval(intvl)

        for node in nodes:
            m = node.get_incoming_link_num()
            for j in range(m):
                # randomly select the first link
                pos = (i + j) % m
                link = node.incoming_links[pos]

                while link.outflow_cap[i] and link.exit_queue:
                    a_no = link.exit_queue[0]
                    agent = A.get_agent(a_no)

                    if agent.get_curr_dep_interval() > i:
                        break

                    if agent.reached_last_link():
                        # link.cum_dep[i] += 1
                        cum_dep += 1
                    else:
                        link_no = agent.get_next_link_no()
                        next_link = links[link_no]
                        next_link.entr_queue.append(a_no)
                        agent.set_dep_interval(i)
                        # set up arrival time for the next link, i.e., next_link
                        agent.set_arr_interval(i, 1)

                        travel_intvl = i - agent.get_arr_interval()
                        waiting_intvl = travel_intvl - A.cast_minute_to_interval(link.get_period_fftt(0))
                        # arrival time in minutes
                        arr_minute = A.cast_interval_to_minute(agent.get_arr_interval())
                        link.update_waiting_time(arr_minute, waiting_intvl)
                        # link.cum_dep[i] += 1
                        # next_link.cum_arr[i] += 1

                    agent.increment_link_pos()
                    # remove agent from exit queue
                    link.exit_queue.popleft()
                    link.outflow_cap[i] -= 1