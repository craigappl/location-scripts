#!/usr/bin/env python3
# coding: utf8
import osmapi
import geojson
import argparse
import os
from datetime import timezone
import configparser
import re
import numpy as np

def create_feature(way, nodes):
    coords = []
    for nodeId in way['data']['nd']:
        node = [node for node in nodes if node['id'] == nodeId][0]
        coords.append([node['lon'], node['lat']])

    tags = way['data']['tag']

    externalId = tags['description'].strip()
    externalParentId = externalId[0:8]
    name = f'{tags["name"].strip()} ({externalId})'
    timestamp = (way['data']['timestamp']).replace(tzinfo=timezone.utc).timestamp()
    source = tags['source'] if 'source' in tags else 'null'

    feat = geojson.Feature(
        geometry={
            "type":"Polygon",
            "coordinates":[coords]
        },
        properties={
            "externalId": externalId,
            "externalParentId": externalParentId,
            "name": name,
            "geographicLevel": '5',
            "source": source,
            "timestamp": timestamp
        }
    )
    return feat


def simplify_node(nodeObj):
    node = {
        'id': nodeObj['data']['id'],
        'lat': nodeObj['data']['lat'],
        'lon': nodeObj['data']['lon']
    }
    return node


def get_ways_by_ids(api, min_id, max_id, source_filter):
    # Create an empty list for geojson features
    feats = []

    # Create lists for possible outcomes
    foundIDs = []
    notFoundIDs = []
    noSourceMatchIDs = []
    otherExceptionIDs = []

    # Loop through way IDs and create geojson features
    for i in range(min_id, max_id + 1):
        print(f'Progress: {round((i-min_id)/(max_id - min_id) * 100, 1)}%', end="\r", flush=True)

        # Try to get the full way information from the api
        try:
            fullWay = api.WayFull(i)

            # Create an empty list forthe nodes and an empty string for the way details
            nodes = []
            way = ""

            # Loop through the fullWay list to separate out the way and it's nodes
            for obj in fullWay:

                # If it's a node, create a dict with the eseential info and append to nodes
                if obj['type'] == 'node':
                    node = simplify_node(obj)
                    nodes.append(node)

                # If it's the way, simply add all the details to the way variable
                if obj['type'] == 'way':
                    if source_filter and not re.match(source_filter, obj['data']['tag']['source']):
                        raise ValueError("Way source tag doesn't match supplied filter")
                    else:
                        way = obj

            # Create a feature from the way details and a list of the nodes and
            # append to the feats list
            feat = create_feature(way, nodes)
            feats.append(feat)
            foundIDs.append(i)
            # print(f'Found way matching index {i}', end="\r", flush=True)

        # If an exception is thrown, print it but keep going through the for loop
        except Exception as e:
            if "404 - Not Found" in str(e):
                notFoundIDs.append(i)
            elif "supplied filter" in str(e):
                noSourceMatchIDs.append(i)
            else:
                otherExceptionIDs.append(i)
                print(f'Exception for id={i}: {e}')
            continue

    # Print the results
    print("")
    print(f'Foci found in ID range: {len(foundIDs)}')
    print(f'Foci not found in ID range: {len(notFoundIDs)}')
    if(len(noSourceMatchIDs) >= 1):
        print(f'Foci found in ID range but do not match provided source filter: {len(noSourceMatchIDs)}')
    if(len(otherExceptionIDs) >= 1):
        print(f'IDs with other exceptions: {len(otherExceptionIDs)}')
    return feats


# def get_ways_by_bbox(api, bbox):
#     # Get all nodes/ways/relations in the bbox
#     map = api.Map(bbox['left'], bbox['bottom'], bbox['right'], bbox['top'])
#
#     # Create empty lists for the nodes and ways
#     nodes = []
#     ways = []
#
#     # Loop through the map result to sort out nodes from ways
#     for d in map:
#         if d['type'] == 'node':
#             node = simplify_node(d)
#             nodes.append(node)
#         if d['type'] == 'way':
#             ways.append(d)
#
#     print(f'Extracted {len(ways)} ways and {len(nodes)} associated nodes')
#
#     # Loop through ways to create features
#     feats = []
#     for w in ways:
#         wayNodeIDs = w['data']['nd']
#         wayNodes = [node for node in nodes if node['id'] in wayNodeIDs]
#         feat = create_feature(w, wayNodes)
#         feats.append(feat)
#
#     return feats


def path_with_geojson(saveLoc):
    separator = "/" if "/" in saveLoc else "\\"
    path = saveLoc.rsplit(separator,1)[0]
    if os.path.isdir(path):
        if not saveLoc.endswith('.geojson'):
            raise argparse.ArgumentTypeError("Output file must end with '.geojson'")
        else:
            return saveLoc
    else:
        raise argparse.ArgumentTypeError(f'The save location ({saveLoc}) is not on a valid path')


def main():

    # Add and parse the main arguments - min and max way IDs and the output file location
    parser = argparse.ArgumentParser(description="Script to create geojson by querying way IDs in local OSM server")
    # parser.add_argument('type', choices=["id","bbox"], help="Type of query - id loops through min/max ids, bbox pulls all values from bbox")
    parser.add_argument('output_file', type=path_with_geojson, help="Output file location, must end with '.geojson'")
    parser.add_argument('--min', dest="min_id", default="1", help="Minimum way ID to check", type=int)
    parser.add_argument('--max', dest="max_id", default="1000", help="Maximum way ID to check", type=int)
    parser.add_argument('-s', '--source', dest="source_filter", help="Regex string of source values to filter on")
    args = parser.parse_args()

    # Read the config.ini file to get the username and password
    config = configparser.ConfigParser()
    config.read('config.ini')

    # Get api for local OSM instance
    url = config['local_osm']['url']
    usr = config['local_osm']['username']
    pw = config['local_osm']['password']
    api = osmapi.OsmApi(api=url, username=usr, password=pw)

    # Print source filter if applicable
    if args.source_filter: print(f'Filtering output by the following source tag(s): {args.source_filter}')

    # If id chosen, run get_ways_by_ids to get a collection of features
    # if args.type == "id":
    print(f'Getting ways with IDs between {args.min_id} and {args.max_id}')
    feats = get_ways_by_ids(api, args.min_id, args.max_id, args.source_filter)

    # # If bbox is chosen, run get_ways_by_bbox to get a collection of features
    # if args.type == "bbox":
    #     bbox = {'left': 97.295,'bottom': 5.397,'right': 105.732,'top': 20.468}
    #     print(f'Getting ways in the following Thai bbox: {bbox}')
    #     feats = get_ways_by_bbox(api, bbox)

    # After getting all the ways, create a feature collection
    fc = geojson.FeatureCollection(feats)

    # Save the feature collection to the output_file location
    with open(args.output_file, 'w', encoding='utf8') as f:
        geojson.dump(fc,f, ensure_ascii=False, indent=4)


if __name__ == '__main__':
    main()
