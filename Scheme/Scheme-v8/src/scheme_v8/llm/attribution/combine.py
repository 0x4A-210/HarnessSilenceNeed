from __future__ import annotations

def combine(maintenance, temporal):
    maintenance_alarm = maintenance['verdict'] == 'needs_update'
    temporal_alarm = temporal['status'] in ('introduced', 'preexisting')
    joint_alarm = maintenance_alarm or (maintenance['verdict'] != 'satisfied_in_scope' and temporal_alarm)
    return {'maintenance_alarm': maintenance_alarm, 'temporal_gap_alarm': temporal_alarm, 'joint_alarm': joint_alarm, 'joint_origin': temporal['status'] if joint_alarm and temporal_alarm else 'unknown' if maintenance_alarm else 'not_applicable'}


def combine_cascade(maintenance_verdict, temporal_status):
    """Cascade engine: timing exists only for a maintenance alarm."""
    alarm = maintenance_verdict == 'needs_update'
    return {'maintenance_alarm': alarm, 'temporal_gap_alarm': alarm and temporal_status in ('introduced', 'preexisting'),
            'joint_alarm': alarm, 'joint_origin': temporal_status if alarm else 'not_applicable'}
