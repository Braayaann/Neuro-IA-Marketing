CREATE TABLE users (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash TEXT NOT NULL, 
	role VARCHAR(10) NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (role IN ('admin','owner')), 
	UNIQUE (email)
);

CREATE TABLE ads (
	id SERIAL NOT NULL, 
	owner_id INTEGER NOT NULL, 
	title VARCHAR(140) NOT NULL, 
	description VARCHAR(500) NOT NULL, 
	color VARCHAR(7) NOT NULL, 
	image VARCHAR(80), 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE INDEX ix_ads_owner_id ON ads (owner_id);

CREATE TABLE studies (
	id SERIAL NOT NULL, 
	owner_id INTEGER NOT NULL, 
	name VARCHAR(140) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	camera_id VARCHAR(300), 
	screen_width INTEGER, 
	screen_height INTEGER, 
	with_emotions BOOLEAN NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	ended_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	last_seq INTEGER NOT NULL, 
	last_elapsed FLOAT, 
	last_ad_id INTEGER, 
	PRIMARY KEY (id), 
	CHECK (status IN ('draft','calibrating','ready','running','completed','cancelled')), 
	FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE INDEX ix_studies_owner_id ON studies (owner_id);

CREATE TABLE calibrations (
	study_id INTEGER NOT NULL, 
	samples JSON NOT NULL, 
	mean JSON, 
	scale JSON, 
	coefficients JSON, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (study_id), 
	FOREIGN KEY(study_id) REFERENCES studies (id)
);

CREATE TABLE study_ads (
	id SERIAL NOT NULL, 
	study_id INTEGER NOT NULL, 
	ad_id INTEGER NOT NULL, 
	position INTEGER NOT NULL, 
	title VARCHAR(140) NOT NULL, 
	description VARCHAR(500) NOT NULL, 
	color VARCHAR(7) NOT NULL, 
	image VARCHAR(80), 
	PRIMARY KEY (id), 
	UNIQUE (study_id, position), 
	UNIQUE (study_id, ad_id), 
	CHECK (position >= 0 AND position <= 3), 
	FOREIGN KEY(study_id) REFERENCES studies (id), 
	FOREIGN KEY(ad_id) REFERENCES ads (id)
);

CREATE INDEX ix_study_ads_study_id ON study_ads (study_id);

CREATE TABLE observations (
	id SERIAL NOT NULL, 
	study_id INTEGER NOT NULL, 
	study_ad_id INTEGER, 
	seq INTEGER NOT NULL, 
	elapsed FLOAT NOT NULL, 
	x FLOAT, 
	y FLOAT, 
	valid BOOLEAN NOT NULL, 
	reason VARCHAR(100) NOT NULL, 
	emotion VARCHAR(20), 
	confidence FLOAT, 
	estimated_seconds FLOAT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (study_id, seq), 
	CHECK (elapsed >= 0), 
	CHECK (estimated_seconds >= 0), 
	FOREIGN KEY(study_id) REFERENCES studies (id), 
	FOREIGN KEY(study_ad_id) REFERENCES study_ads (id)
);

CREATE INDEX ix_observations_study_ad_id ON observations (study_ad_id);

CREATE INDEX ix_observations_study_id ON observations (study_id);
