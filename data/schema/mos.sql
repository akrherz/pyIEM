-- Storage of MOS data
CREATE TABLE alldata(
 station character(4)           ,
 model character varying(12)  ,
 runtime timestamp with time zone ,
 ftime  timestamp with time zone ,
 n_x   smallint           ,
 tmp    smallint             ,
 dpt     smallint               ,
 cld    character(2)         ,
 wdr    smallint             ,
 wsp   smallint          ,
 p06   smallint             ,
 p12    smallint             ,
 q06   smallint              ,
 q12   smallint       ,
 t06_1   smallint         ,
 t06_2   smallint        ,
 t12_1   smallint         ,
 t12_2   smallint     ,
 snw    smallint         ,
 cig    smallint      ,
 vis   smallint          ,
 obv  character(2)  ,
 poz    smallint           ,
 pos    smallint        ,
 typ    character(2),
  sky smallint,
  gst smallint,
  t03 smallint,
  pzr smallint,
  psn smallint,
  ppl smallint,
  pra smallint,
  s06 smallint,
  slv smallint,
  i06 smallint,
  lcb smallint,
  swh smallint
);
GRANT ALL on alldata to mesonet,ldm;
GRANT SELECT on alldata to nobody,apache;

create table t2017(
  CONSTRAINT __t2017_check
  CHECK(runtime >= '2017-01-01 00:00+00'::timestamptz
        and runtime < '2018-01-01 00:00+00'::timestamptz))
  INHERITS (alldata);
CREATE INDEX t2017_idx on t2017(station, model, runtime);
CREATE INDEX t2017_runtime_idx on t2017(runtime);
GRANT SELECT on t2017 to nobody,apache;
GRANT ALL on t2017 to mesonet,ldm;

create table t2018(
  CONSTRAINT __t2018_check
  CHECK(runtime >= '2018-01-01 00:00+00'::timestamptz
        and runtime < '2019-01-01 00:00+00'::timestamptz))
  INHERITS (alldata);
CREATE INDEX t2018_idx on t2018(station, model, runtime);
CREATE INDEX t2018_runtime_idx on t2018(runtime);
GRANT SELECT on t2018 to nobody,apache;
GRANT ALL on t2018 to mesonet,ldm;
