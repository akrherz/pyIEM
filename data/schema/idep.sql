CREATE TABLE scenarios(
    id int,
    label varchar,
    climate_scenario int,
    huc12_scenario int
);
GRANT SELECT on scenarios to nobody;
INSERT into scenarios values (0, 'Production', 0, 0);
