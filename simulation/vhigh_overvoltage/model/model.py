#!/usr/bin/env python3
"""TWIST power leg, averaged model (level D: fast evaluation of ideas, never a hardware verdict).

One leg: Q201 (high side, IPD200N15N3) / Q202, L201 33 uH, VHigh caps per leg, lab supply on VHigh
through a cable. Averaged over a switching period: no ripple, no device physics, no parasitic ringing
except a fixed L*di/dt turn-off spike added to Vds(Q201).

States: iL (L201, + = buck direction SW -> low side), vH (VHigh caps), iC (cable, PSU -> VHigh),
        vL (low-side capacitor: 'cap' = C_low || R_load, 'motor' = motor + rider as an equivalent capacitor).
The board is self-powered from VHigh (Feeder via JP5001): PWM keeps running while vH > V_feeder_min.
"""
import math
import numpy as np

BASE = dict(
    L=33e-6, R_L=0.02, C_H=138e-6,
    Vs=100.0, R_cab=0.05, L_cab=1e-6,
    psu_can_sink=False, t_dis=None,          # None: never disconnected
    low='battery', V_low=48.0, R_low=0.05,   # 'battery' | 'cap' | 'motor'
    C_low=60e-6, R_load=6.0, C_mot=3.0, R_mot=0.1,
    mode='current', I_ref=8.0,               # 'current' (PI loop on iL) | 'duty' (open loop)
    d0=0.48, d_step=None, t_step=1e-3,
    duty_slew=None,                          # max |dd/dt| in 1/s (None: unlimited)
    i_limit=None,                            # cycle-by-cycle |iL| limit in A (None: none)
    ov_trip=None, trip_delay=0.0,            # VHigh overvoltage: PWM off (latched) after the delay
    v_clamp=None,                            # proposed drain-gate active clamp on Q201 (zener voltage)
    V_feeder_min=8.9,
    L_loop=10e-9, di_dt=0.5e9,
    V_rating=150.0, V_absmax=110.0, I_rating=40.0, E_clamp_max=0.15,
    t_end=10e-3, dt=50e-9, rec_every=40,
)


def run(p):
    """@return dict: traces (t, vH, iL, d, iC, vL, pwm, p_clamp) and summary numbers."""
    p = {**BASE, **p}
    L, C_H, dt = p['L'], p['C_H'], p['dt']
    vH = p['Vs']
    if p['low'] in ('battery', 'motor'):
        vL = p['V_low']
    else:
        vL = p['d0'] * p['Vs']
    if p['mode'] == 'current':
        iL = p['I_ref']
    elif p['low'] == 'cap':
        iL = vL / p['R_load']
    else:
        iL = (p['d0'] * p['Vs'] - p['V_low']) / (p['R_L'] + p['R_low'])
    vLt0 = vL + (p['R_low'] if p['low'] == 'battery' else p['R_mot'] if p['low'] == 'motor' else 0) * iL
    d = (vLt0 + iL * p['R_L']) / vH if p['mode'] == 'current' else p['d0']
    iC = d * iL
    integ = d
    kp = 2 * math.pi * 2000 * L / p['Vs']
    ki = kp * 2 * math.pi * 200
    pwm_on, trip_t, ov_seen, e_clamp = True, None, None, 0.0
    t_150 = None
    n = int(p['t_end'] / dt)
    rec = {k: [] for k in ('t', 'vH', 'iL', 'd', 'iC', 'vL', 'pwm', 'p_clamp')}
    vds_pk, iL_pk, d_prev, p_cl = vH, abs(iL), d, 0.0
    for k in range(n):
        t = k * dt
        connected = p['t_dis'] is None or t < p['t_dis']
        # control
        if p['mode'] == 'current':
            e = p['I_ref'] - iL
            integ = min(1.0, max(0.0, integ + ki * e * dt))
            d_cmd = min(1.0, max(0.0, integ + kp * e))
        else:
            d_cmd = p['d_step'] if (p['d_step'] is not None and t >= p['t_step']) else p['d0']
        if p['duty_slew'] is not None:
            step = p['duty_slew'] * dt
            d_cmd = min(d_prev + step, max(d_prev - step, d_cmd))
        d = d_cmd
        # protection
        if p['ov_trip'] is not None and ov_seen is None and vH > p['ov_trip']:
            ov_seen = t
        if ov_seen is not None and pwm_on and t >= ov_seen + p['trip_delay']:
            pwm_on, trip_t = False, t
        if vH < p['V_feeder_min']:
            pwm_on = False
        # low-side terminal voltage
        if p['low'] == 'battery':
            vLt = p['V_low'] + p['R_low'] * iL
        elif p['low'] == 'motor':
            vLt = vL + p['R_mot'] * iL
        else:
            vLt = vL
        # inductor
        if pwm_on:
            diL = (d * vH - vLt - p['R_L'] * iL) / L
            if p['i_limit'] is not None and abs(iL) >= p['i_limit'] and diL * iL > 0:
                # cycle-by-cycle limit: the period is cut short, the effective duty holds the current
                d = (vLt + p['R_L'] * iL) / vH
                diL = 0.0
            iH = d * iL
        else:
            if iL > 0:
                vsw = 0.0
            elif iL < 0:
                vsw = vH
            else:
                vsw = vH if vLt > vH else None
            diL = 0.0 if vsw is None else (vsw - vLt - p['R_L'] * iL) / L
            iH = iL if vsw == vH else 0.0
        d_prev = d
        iL_new = iL + diL * dt
        if not pwm_on and iL != 0 and iL_new * iL < 0:
            iL_new = 0.0
        # cable / PSU
        if connected:
            iC += (p['Vs'] - vH - p['R_cab'] * iC) / p['L_cab'] * dt
            if not p['psu_can_sink'] and iC < 0:
                iC = 0.0
        else:
            iC = 0.0
        vH += (iC - iH) / C_H * dt
        # proposed active clamp: Q201 conducts (linear) whatever keeps VHigh at v_clamp
        p_cl = 0.0
        if p['v_clamp'] is not None and vH > p['v_clamp']:
            i_cl = (vH - p['v_clamp']) * C_H / dt
            vH = p['v_clamp']
            p_cl = p['v_clamp'] * i_cl
            e_clamp += p_cl * dt
        if p['low'] == 'cap':
            vL += (iL - vL / p['R_load']) / p['C_low'] * dt
        elif p['low'] == 'motor':
            vL += iL / p['C_mot'] * dt
        iL = iL_new
        spike = p['L_loop'] * p['di_dt'] if (pwm_on and iL > 0) else 0.0
        vds = vH + spike
        if vds > vds_pk:
            vds_pk = vds
        if t_150 is None and vds > p['V_rating']:
            t_150 = t
        iL_pk = max(iL_pk, abs(iL))
        if k % p['rec_every'] == 0:
            for key, v in (('t', t), ('vH', vH), ('iL', iL), ('d', d if pwm_on else float('nan')),
                           ('iC', iC), ('vL', vL if p['low'] != 'battery' else vLt),
                           ('pwm', 1.0 if pwm_on else 0.0), ('p_clamp', p_cl)):
                rec[key].append(v)
    tr = {k: np.asarray(v) for k, v in rec.items()}
    return dict(traces=tr, vds_pk=vds_pk, iL_pk=iL_pk, trip_t=trip_t, t_150=t_150,
                e_clamp=e_clamp, p_clamp_pk=float(tr['p_clamp'].max()), vH_end=float(tr['vH'][-1]), p=p)
