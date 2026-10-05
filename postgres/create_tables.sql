-- CREATE DATABASE openagri_edge
--     WITH
--     OWNER = openagri_user
--     ENCODING = 'UTF8'
--     LC_COLLATE = 'en_US.utf8'
--     LC_CTYPE = 'en_US.utf8'
--     LOCALE_PROVIDER = 'libc'
--     TABLESPACE = pg_default
--     CONNECTION LIMIT = -1
--     IS_TEMPLATE = False;

CREATE TABLE IF NOT EXISTS projects
(
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS flights
(
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE,
    project_id integer REFERENCES projects(id) ON DELETE CASCADE,
    environment text NOT NULL,
    timestamp_epoch integer NOT NULL
);

CREATE TABLE IF NOT EXISTS images
(
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    flight_id integer REFERENCES flights(id) ON DELETE CASCADE,
    storage_location text NOT NULL,
    gps_location point NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    model_runtime real
);

CREATE TABLE IF NOT EXISTS detections
(
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    image_id integer REFERENCES images(id) ON DELETE CASCADE,
    confidence real NOT NULL,
    position point NOT NULL,
    storage_location text NOT NULL
);
