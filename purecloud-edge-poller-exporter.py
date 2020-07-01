# -*- coding: UTF-8 -*-
from prometheus_client import start_http_server, Gauge, Summary
import PureCloudPlatformClientV2
import configparser
import sys
import time
import json
import requests

# Define metrics
ONLINE_STATUS = Gauge('genesys_online_status', 'Online Status',['instance'])
OUT_CALLS = Gauge('genesys_out_calls_num', 'Outbound calls', ['instance'])
IN_CALLS = Gauge('genesys_in_calls_num', 'Inbound calls', ['instance'])
WAN_REC = Gauge('genesys_wan_rec_bytes', 'WAN received bytes/s', ['instance']) 
WAN_SENT = Gauge('genesys_wan_sent', 'WAN sent bytes/s', ['instance']) 
LAN_REC = Gauge('genesys_lan_rec', 'LAN received bytes/s', ['instance']) 
LAN_SENT = Gauge('genesys_lan_sent', 'LAN sent bytes/s', ['instance']) 

# Read config.ini and parse
# If no values found, use hard coded values
config = configparser.ConfigParser()
config.read('config.ini')

try:
	port = int(config.get('DEFAULT','port'))
except:
	print("port undefined, using 9100")
	port = 9100
if (port < 1024 or port > 65536):
	print ("Port number " + str(port) + " invalid, must be between 1024 - 65536")
	print ("Please check config.ini!")
	exit()

try:
	poll_interval = int(config.get('DEFAULT','poll_interval'))
except:
	print ("poll_interval undefined, using 30 sec")
	poll_interval = 30
if (poll_interval < 15):
	print ("Poll interval " + str(poll_interval) + " too short, must be above 15 seconds")
	print ("Please check config.ini!")
	exit()
	
try:
	servers = json.loads(config.get('DEFAULT','servers'))
except:
	print ("servers undefined, using 0401,0501,0601")
	servers = json.loads('["edge-se-0401","edge-se-0501","edge-se-0601"]')

# Login to Purecloud
region = PureCloudPlatformClientV2.PureCloudRegionHosts.eu_central_1
PureCloudPlatformClientV2.configuration.host = region.get_api_host()

apiclient = PureCloudPlatformClientV2.api_client.ApiClient().get_client_credentials_token(token, secret)
authApi = PureCloudPlatformClientV2.AuthorizationApi(apiclient)

EdgeApi = PureCloudPlatformClientV2.TelephonyProvidersEdgeApi(apiclient)

def collect():
  # Get Edge info
  apiResponse = EdgeApi.get_telephony_providers_edges().to_json()
  apiResponse = json.loads(apiResponse)

  # Get online status and bw
  for edge in apiResponse['entities']:
      if (edge['name'] in servers):
          print (edge['name'])
          if (edge['online_status'] == "ONLINE"):
              online_status = 1
          else:
              online_status = 0 
          bw = EdgeApi.get_telephony_providers_edge_metrics(edge['id']).to_json()
          bw = json.loads(bw)
          for interface in bw['networks']:
              if (interface['ifname'] == "eno1"):
                      wan_rec_mbits = interface['received_bytes_per_sec']
                      wan_sent_mbits = interface['sent_bytes_per_sec']
              elif (interface['ifname'] == "eno2"):
                      lan_rec_mbits = interface['received_bytes_per_sec']
                      lan_sent_mbits = interface['sent_bytes_per_sec']
          # Get numbers of calls for all trunks per edge
          trunks = EdgeApi.get_telephony_providers_edge_trunks(edge['id']).to_json()
          trunks = json.loads(trunks)
          in_calls = 0
          out_calls = 0
          for trunk in trunks['entities']:
            if (trunk['connected_status']):
              trunkMetrics = EdgeApi.get_telephony_providers_edges_trunk_metrics(trunk['id']).to_json()
              trunkMetrics = json.loads(trunkMetrics)
              in_calls = in_calls + trunkMetrics['calls']['inbound_call_count']
              out_calls = out_calls + trunkMetrics['calls']['outbound_call_count']

          # Export to Prometheus
          ONLINE_STATUS.labels(edge['name']).set(online_status)
          OUT_CALLS.labels(edge['name']).set(out_calls)
          IN_CALLS.labels(edge['name']).set(in_calls)
          WAN_REC.labels(edge['name']).set(wan_rec_mbits)
          WAN_SENT.labels(edge['name']).set(wan_sent_mbits)
          LAN_REC.labels(edge['name']).set(lan_rec_mbits)
          LAN_SENT.labels(edge['name']).set(lan_sent_mbits)

if __name__ == '__main__':
  if len(sys.argv) != 1:
      print('Usage: edge_exporter.py')
      exit(1)
  else:
    try:
        start_http_server(port)
        while True: 
          collect()
          time.sleep(poll_interval)
    except KeyboardInterrupt:
        exit(0)