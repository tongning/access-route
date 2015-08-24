

## access-route

### Introduction
access-route is a routing/navigation website similar to Google Maps, but with a focus on accessibility. Users can search for a start and destination address and the website will display the shortest route that bypasses accessibility obstacles. It is written in Django python with street network data, obstacle data, and elevation data stored in Postgres/PostGIS. Shortest routes are calculated using the Dijkstra algorithm in PgRouting.

The map is drawn using the Mapbox API with data from OpenStreetMap. Routes and markers on the map are drawn with leaflet.js.

Features:

 * Start and end address search, powered by OpenCage API
 * Graph of elevation along route, drawn using d3.js
 * Accessibility obstacles marked on map with clickable pins; links to Google Street View imagery
 * Customizable cost calculation algorithm for routing
 
### Installation/Usage

#### Notes
This guide assumes that you have street network data in geojson format, and information about the locations of accessibility features/obstacles in geojson files with a different file for each type of feature. If you have the data a different format, you may have to do some conversions or make adjustments to the instructions below.

#### Python
Required Python 3.4 packages are listed in requirements.txt and can usually be installed with pip. It is probably best to set this up in a new Virtual Environment.

#### Database
Due to extensive use of PostGIS functions which don't fit well into Django models, this application performs raw SQL queries. Unfortunately, this means the appropriate database tables must be set up manually.

##### Basic setup

1. Install Postgres and [PostGIS](http://postgis.net/install/)
2. Create a new Postgres database named `routing`
3. Enable PostGIS in the `routing` database:
```sql
-- Enable PostGIS (includes raster)
CREATE EXTENSION postgis;
-- Enable Topology
CREATE EXTENSION postgis_topology;
-- fuzzy matching needed for Tiger
CREATE EXTENSION fuzzystrmatch;
-- Enable US Tiger Geocoder
CREATE EXTENSION postgis_tiger_geocoder;
```
4. Enable PgRouting functions:
``` sql
-- add pgRouting core functions
CREATE EXTENSION pgrouting; 
```

##### Add the required tables:

`sidewalk_edge` stores the street network on which routes will be calculated. For details on how to create and populate this database, scroll down to **Importing the street network data**.


`feature_types` stores the types of accessibility features that can be present on the map.
```sql
CREATE TABLE public.feature_types
(
  type_id integer NOT NULL DEFAULT nextval('feature_types_type_id_seq'::regclass),
  type_string character varying(150),
  CONSTRAINT feature_types_pkey PRIMARY KEY (type_id)
)
WITH (
  OIDS=FALSE
);
ALTER TABLE public.feature_types
  OWNER TO postgres;
```
After creating the table, you should add, at minimum, the following two entries:

| type_id | type_string  |
|---------|--------------|
| 1       | curbcut      |
| 2       | construction |

`accessibility_feature` stores accessibility features and their locations. After creating it, this table can be populated using a python script. Scroll down to **Populating accessibility features** for details.
```sql
CREATE TABLE public.accessibility_feature
(
  accessibility_feature_id integer NOT NULL DEFAULT nextval('accessibility_features_feature_id_seq'::regclass),
  feature_geometry geometry(Point,4326),
  feature_type integer,
  lng double precision,
  lat double precision,
  CONSTRAINT accessibility_features_pkey PRIMARY KEY (accessibility_feature_id),
  CONSTRAINT accessibility_feature_feature_type_fkey FOREIGN KEY (feature_type)
      REFERENCES public.feature_types (type_id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION
)
WITH (
  OIDS=FALSE
);
ALTER TABLE public.accessibility_feature
  OWNER TO postgres;
```

`sidewalk_edge_accessibility_feature` keeps track of which accessibility features belong to which streets. This table can also be populated automatically after creation; scroll down to **Populating accessibility features** for details.
```sql
CREATE TABLE public.sidewalk_edge_accessibility_feature
(
  sidewalk_edge_accessibility_feature_id integer NOT NULL DEFAULT nextval('sidewalk_edge_accessibility_f_sidewalk_edge_accessibility_f_seq'::regclass),
  sidewalk_edge_id integer,
  accessibility_feature_id integer,
  CONSTRAINT sidewalk_edge_accessibility_feature_pkey PRIMARY KEY (sidewalk_edge_accessibility_feature_id),
  CONSTRAINT sidewalk_edge_accessibility_feature_accessibility_feature_id_fk FOREIGN KEY (accessibility_feature_id)
      REFERENCES public.accessibility_feature (accessibility_feature_id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION
)
WITH (
  OIDS=FALSE
);
ALTER TABLE public.sidewalk_edge_accessibility_feature
  OWNER TO postgres;

```
The `elevation` table stores the elevation data used to generate a graph of elevation along a route. I obtained data from the [USGS National Map Viewer](http://viewer.nationalmap.gov/viewer/) - if you want to use elevation data from here, download it in IMG format and you can use a python script in this repository to automatically import it into the `elevation` table. See **Importing USGS elevation data** for details. If you're using data in a different format, you'll have to figure out a different way to populate this table. It has three columns which are pretty self-explanatory:
* lat (double precision)
* long (double precision)
* elevation (double precision) - in meters

```sql

CREATE TABLE public.elevation
(
  lat double precision NOT NULL,
  "long" double precision NOT NULL,
  elevation double precision,
  CONSTRAINT elevation_pkey PRIMARY KEY (lat, long)
)
WITH (
  OIDS=FALSE
);
ALTER TABLE public.elevation
  OWNER TO postgres;

CREATE INDEX combined_index
  ON public.elevation
  USING btree
  (lat, long);

CREATE INDEX lat_index
  ON public.elevation
  USING btree
  (lat);

CREATE INDEX lng_index
  ON public.elevation
  USING btree
  (long);
```





