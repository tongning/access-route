from django.shortcuts import render
from django.http import HttpResponse
from django.core.urlresolvers import reverse
from django.db import connection
from opencage.geocoder import OpenCageGeocode
import json
import logging
import geojson
import math
logger = logging.getLogger(__name__)
# Create your views here.
global_start_lat = 0
global_end_lat = 0
global_start_lng = 0
global_end_lng = 0
def homepage(request):
    default_startaddr = "Enter start address"
    default_endaddr = "Enter end address"
    routegeojson = """{
    "type": "FeatureCollection",
    "features": []
    }"""
    average_lat = 38.89
    average_lng = -77.044
    defaultzoom = 11
    return render(request, 'routeapp/homepage.html', {'centerlat':average_lat, 'centerlng':average_lng, 'defaultzoom': defaultzoom, 'start_textbox_value': default_startaddr, 'dest_textbox_value': default_endaddr, 'routegeojson': routegeojson,})

def elevationgeojson(request):
    return render(request, 'routeapp/elevation.geojson', {})
    
def routegeojson(request):
    return render(request, 'routeapp/route.geojson', {})
def search(request):
    
    address = request.GET['inputaddress'].strip()
    dest = request.GET['inputdest'].strip()
    error=""
    startfound = True
    destfound = True
    lat=0
    lng=0
    destlat=0
    destlng=0
    routegeojson = """{
    "type": "FeatureCollection",
    "features": []
    }"""
    # Query OpenCage to get coordinates for this address
    key = '7945028e977fa9593e5b02378cbf0f27'
    geocoder = OpenCageGeocode(key)
    if (address != '' and dest != ''):
        # Get coordinates for start address
        jsonresult = geocoder.geocode(address)
        
        try:
            resultdict = jsonresult[0]
            lat = resultdict["geometry"]["lat"]
            lng = resultdict["geometry"]["lng"]
        except IndexError:
            startfound = False
        
        # Get coordinates for destination address
        jsonresult = geocoder.geocode(dest)
        try:
            resultdict = jsonresult[0]
            destlat = resultdict["geometry"]["lat"]
            destlng = resultdict["geometry"]["lng"]
        except IndexError:
            destfound = False
        
        if not startfound and destfound:
            error = "Error: The start address you entered could not be found."
        elif startfound and not destfound:
            error = "Error: The end address you entered could not be found."
        elif not startfound and not destfound:
            error = "Error: Neither addresses you entered could be found."
    else:
        error = "Error: One or more fields were left blank."
    # Perform raw query to postgres database to find sidewalk closest to start coordinates
    cursor = connection.cursor()
    
    cursor.execute("SELECT source FROM sidewalk_edge ORDER BY ST_Distance(ST_GeomFromText('POINT(%s %s)', 4326), wkb_geometry) ASC LIMIT 1", [lng, lat])
    row = cursor.fetchone()
    start_edge_id = row[0]
    # Repeat to find sidewalk closest to end coordinates
    cursor.execute("SELECT target FROM sidewalk_edge ORDER BY ST_Distance(ST_GeomFromText('POINT(%s %s)', 4326), wkb_geometry) ASC LIMIT 1", [destlng, destlat])
    row = cursor.fetchone()
    end_edge_id = row[0]
    print("Start edge id is "+str(start_edge_id))
    print("End edge id is   "+str(end_edge_id))
    # Find location in the middle of the route for centering the map
    average_lat = (lat + destlat)/2.0
    average_lng = (lng + destlng)/2.0
    # Create geojson route
    routesql = """
    SELECT ST_AsGeoJSON(st_union) FROM (
    SELECT ST_Union(wkb_geometry) FROM (
    SELECT seq, id1 AS node, id2 AS edge, route.cost, dt.wkb_geometry, dt.sidewalk_edge_id FROM pgr_dijkstra('
                SELECT sidewalk_edge_id AS id,
                         source::integer,
                         target::integer,
                         calculate_accessible_cost(sidewalk_edge_id)::double precision AS cost
                        FROM sidewalk_edge',
                %s, %s, false, false) as route
				join sidewalk_edge  dt
				on route.id2 = dt.sidewalk_edge_id
    ) as routegeometries
    ) as final; """
    cursor.execute(routesql, [start_edge_id, end_edge_id])
    row = cursor.fetchone()
    routejs = row[0]
    # We now have the geojson representing the route, but we need to clean it up a little
    geojson_dirty = json.loads(routejs)
    print("Info from route:")
    print(geojson_dirty['coordinates'][-1])
    '''
    # Take all coordinates and combine into a single large list
    coordinates_all = []
    for path in geojson_dirty['coordinates']:
        for point in path:
            pointlng = point[0]
            pointlat = point[1]
            coordinates_all.append(round(pointlng,4))
            coordinates_all.append(round(pointlat,4))
    print(coordinates_all)
    for path in geojson_dirty['coordinates']:
        for point in path:
            pointlng = point[0]
            poitnlng = point[1]
            # See if this is the only occurrence of this point
            if (coordinates_all.count(round(pointlng,4)) == 1 and coordinates_all.count(round(pointlat,4)) == 1):
                print("Found point that only occurs once")
                print(point[0],point[1])
    '''
    # Query the elevation table to get geojson with elevation data
    '''
    data = json.loads(routejs)
    points = []
    for path in data['coordinates']:
        for point in path:
            points.append(point)
    split_path = split(points)
    elevation_list = get_elevations(split_path)
    output_string = output_geojson(input_path, input_elevation_list)
    logger.debug(output_string)
    print(output_string)
    '''
    
    logger.error(routejs)
    routegeojson = routejs
    # print(routejs)
    return render(request, 'routeapp/homepage.html', {'centerlat':average_lat, 'centerlng':average_lng, 'defaultzoom': '17', 'lat':lat, 'lng':lng, 'destlat': destlat, 'destlng':destlng, 'start_textbox_value': address, 'dest_textbox_value': dest, 'error_message':error, 'routegeojson':routegeojson, })

def output_geojson(input_path, input_elevation_list):
    featurelist = []
    # Convert the input path to a python LineString
    path_linestring = LineString(input_path)
    # Create a feature from path_linestring
    feature = geojson.Feature(geometry=path_linestring, properties={"elevation": input_elevation_list})
    featurelist.append(feature)
    FeatureClct = geojson.FeatureCollection(featurelist)
    # Encode FeatureCollection as JSON
    dump = geojson.dumps(FeatureClct, sort_keys=True)
    return dump
    
def get_elevations(input_path):
    output_elevations = []
    
    cursor = connection.cursor()
    for point in input_path:
        lon = abs(point[0])
        lat = abs(point[1])

        query = """SELECT elevation FROM elevation WHERE lat =
                    (
                    SELECT lat FROM
                    (
                        (SELECT lat,long,elevation FROM elevation WHERE lat >= %s ORDER BY lat LIMIT 1)
                        UNION ALL
                        (SELECT lat,long,elevation FROM elevation WHERE lat < %s ORDER BY lat DESC LIMIT 1)
                    ) as nearestlat ORDER BY abs(%s-lat) LIMIT 1
                    )
                AND long =
                (
                    SELECT long FROM
                    (
                        (SELECT lat,long,elevation FROM elevation WHERE long >= %s ORDER BY long LIMIT 1)
                        UNION ALL
                        (SELECT lat,long,elevation FROM elevation WHERE long < %s ORDER BY long DESC LIMIT 1)
                    ) as nearestlong ORDER BY abs(%s-long) LIMIT 1
                )"""
        cursor.execute(query,[lat,lat,lat,lon,lon,lon])
        results = cursor.fetchall()
        for elevation in results:
            output_elevations.append(elevation[0])
    return output_elevations
def split(path_to_split):
    """
    Takes a path, represented as an array of coordinates, and
    split it into smaller segments.
    :param path_to_split:
    :return:
    """
    idx1 = 0
    idx2 = 1
    complete = False
    while not complete:
        complete = True
        while idx2 < len(path_to_split):
            point1 = path_to_split[idx1]
            point2 = path_to_split[idx2]
            x1 = point1[0]
            y1 = point1[1]
            x2 = point2[0]
            y2 = point2[1]
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist > 0.00003:
                complete = False
                new_x = (x1 + x2)/2
                new_y = (y1 + y2)/2
                new_point = [new_x, new_y]
                path_to_split.insert(idx2, new_point)
            idx1 += 1
            idx2 += 1
    return path_to_split