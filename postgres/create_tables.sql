CREATE DATABASE openagri_edge
    WITH
    OWNER = openagri_user
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8'
    LOCALE_PROVIDER = 'libc'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1
    IS_TEMPLATE = False;

CREATE TABLE IF NOT EXISTS projects
(
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS measurements
(
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id integer REFERENCES projects(id),
    timestamp_epoch integer NOT NULL
);

CREATE TABLE IF NOT EXISTS images
(
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    measurement_id integer REFERENCES measurements(id),
    storage_locaton text NOT NULL,
    gps_location point NOT NULL,
    model_runtime real NOT NULL
);

CREATE TABLE IF NOT EXISTS detections
(
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    image_id integer REFERENCES images(id),
    confidence real NOT NULL,
    position point NOT NULL,
    storage_location text NOT NULL
);

