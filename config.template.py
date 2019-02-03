
praw_config = {
	'site_name': None,
	'client_id': ...,
	'client_secret': ...,
	'username': ...,
	'password': ...,
	'user_agent': ...
}
praw_config = {k: v for k, v in praw_config.items() if v is not None}

target_subreddits = [...]

db_url = ...
