# MyRNVPlan
This is a website which displays and queries the current departure times for all public transport stations in the Rhine-Neckar region operated by Rhein-Neckar-Verkehrs GmbH (RNV). 

A live version of this project can be found at: https://plan.al3xst.de

### Features

To display multiple stations at once, just add the stations name after the url, separated by `/`  
For example: https://plan.al3xst.de/Bismarckplatz/HD%20Hauptbahnhof/Rohrbach%20Süd  
But you can use also the shortnames from the mainpage: https://plan.al3xst.de/BHBP/BHHF/RSRS

You can also display only selected platforms for each station. To do this, just provide all platforms you want to see, sperated also by `/` after the respective station.  
For example: https://plan.al3xst.de/Bismarckplatz/1/2/3/RSRS  
This will display only the platforms Steig A, Steig B and Steig C for Bismarckplatz and every Platform for Rohrbach Süd (RSRS is the shortname of the station Rohrbach Süd). The platform numerical ids correspond (unfortunalty only mostly, I'm still trying to find out, what the IDs are for _all_ stations. For example platform id 11 corresponds on Bismarckplatz to Steig B for the line 5 and platform id 12 corresponds to Steig A for the line 5...) to the alphabetical id. Steig A has ID 1, Steig B has ID 2 etc.

I'm still trying to figure out a more convenient way to use these features, besides having to manually edit the URL. I don't want to just add any JS library which may do the job. My highest priority is to keep the site as simple as possible and also not to load huge and heavy frameworks to solve some small inconveniences...

## Requirements
`python3`
A webserver, for example `nginx`, or `apache`.

Python3 Packages:
```
Flask
multi_key_dicts
pyrnvapi  (<- This can be found at https://github.com/MyRNVPlan/pyrnvapi)
```

## Setup

Here I describe how you can setup this project under Linux. Windows shouldn't be much different, you have to look up how to pass environment variables to the python application.

1. You need an API key from Rhein-Neckar-Verkehr GmbH which you can get at https://opendata.rnv-online.de/startinfo-api
2. Now you need to pass the API Key to the environment variable RNV_API_KEY `export RNV_API_KEY=your_api_key_here`
3. Start the application `python3 main.py`

After some seconds, you should see the message:  
` * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)`  

With nginx (or any other webserver) you can setup a reverse proxy, so people from the outside can access the application you just started.

A sample nginx configuration would look like this:  
/etc/nginx/sites-available/myrnvplan
```
server {
  listen [::]:80; #ipv6
  listen 80; #ipv4
  #non ssl here, for smaller example, but please, use SSL! -> look up letsencrypt
  
  server_name subdomain.yourwebdomain.tld;
  
  location / {
    proxy_pass http://127.0.0.1:5000/;
    proxy_redirect http://subdomain.yourwebdomain.tld;
  }
}
```
With this config enabled, everyone accessing `http://subdomain.yourwebdomain.tld` will access the site, running on `http://127.0.0.1:5000` on that machine.

## Licensing
The `pyrnvapi` package which is used in this project, uses the REST Start.Info API from Rhein-Neackar-Verkehr GmbH.  
That API is released under dl-de/by-2-0. See https://www.govdata.de/dl-de/by-2-0 for more information.  
URL to Start.Info API: https://opendata.rnv-online.de/startinfo-api

This project is licensed under the MIT License. See [LICENSE.txt](LICENSE.txt) for more information!

