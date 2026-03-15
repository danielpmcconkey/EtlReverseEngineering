

with jobs as (
	select 
		job_id, 
		case when status = 'COMPLETE' then '10 - COMPLETE'  when status = 'RUNNING' then '01 -RUNNING' end as  status,
		conditional_counts
	from control.re_job_state
	where job_id not like 'val-%'
), all_steps as (
 	select 
	 	tq.job_id,
		j.status as job_status,
		tq.node_name,
		tq.status as step_status,
		tq.created_at,
		tq.claimed_at,
		tq.completed_at,
		conditional_counts,
		case when tq.completed_at is null 
			then NOW() - tq.claimed_at 
			else tq.completed_at - tq.claimed_at
			end as run_duration,
		row_number() over (partition by tq.job_id order by tq.created_at desc) as ordinal
	from jobs j left join control.re_task_queue tq
		on j.job_id = tq.job_id
)
select 
	job_id,
	job_status,
	node_name,
	step_status,
	created_at,
	claimed_at,
	completed_at,
	run_duration,
	conditional_counts	
from all_steps where ordinal = 1
order by job_status, job_id
limit 110