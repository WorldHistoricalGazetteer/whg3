// /whg/webpack/js/review.js

import './extend-maptiler-sdk.js'; // Adds 'fitViewport' method
import datasetLayers from './mapLayerStyles';
import { bbox } from './6.5.0_turf.min.js';
import { attributionString, startSpinner } from './utilities';
import { acmeStyleControl, CustomAttributionControl } from './customMapControls';
import { getPlace } from './getPlace';

import '../css/maplibre-common.css';
import '../css/style-control.css';
import '../css/review.css';

let style_code;
if (mapParameters.styleFilter.length == 0) {
	style_code = ['DATAVIZ', 'DEFAULT']
} else {
	style_code = mapParameters.styleFilter[0].split(".");
}

maptilersdk.config.apiKey = mapParameters.mapTilerKey;
let mappy = new maptilersdk.Map({
	container: mapParameters.container,
	center: mapParameters.center,
	zoom: mapParameters.zoom,
	minZoom: mapParameters.minZoom,
	maxZoom: mapParameters.maxZoom,
	style: maptilersdk.MapStyle[style_code[0]][style_code[1]],
	attributionControl: false,
	geolocateControl: false,
	navigationControl: mapParameters.controls.navigation,
	userProperties: true,
	bearing: 0,
	pitch: 0,
});

let styleControl;
let featureCollection;
let nullCollection = {
    type: 'FeatureCollection',
    features: []
}

function waitMapLoad() {
    return new Promise((resolve) => {
        mappy.on('load', () => {
            console.log('Map loaded.');
			const whgMap = document.getElementById(mapParameters.container);
			
			if (mapParameters.styleFilter.length !== 1) {
				styleControl = new acmeStyleControl(mappy);
				mappy.addControl(styleControl, 'top-right');
			}		
            
            mappy.addSource('places', {
				'type': 'geojson',
			    'data': nullCollection,
				'attribution': attributionString(),
			});
		    datasetLayers.forEach(layer => {
				mappy.addLayer(layer);
			});
			
			mappy.addControl(new CustomAttributionControl({
				compact: true,
		    	autoClose: mapParameters.controls.attribution.open === false,
			}), 'bottom-right');
			
			whgMap.style.opacity = 1;
            
            resolve();
        });
    });
}

function waitDocumentReady() {
    return new Promise((resolve) => {
        $(document).ready(() => resolve());
    });
}

Promise.all([waitMapLoad(), waitDocumentReady()])
    .then(() => {
		
		console.log("already: {{ already }}")
		if ("{{ already }}") {
			alert('last record was saved by someone else, this is the next')
		}
		current_place = $('input[name=place_id]').val()
		console.log('lastPlace:', sessionStorage.lastPlace)
		console.log('current place:', $('input[name=place_id]').val())
		// show undo link if there is a lastPlace & it's not the current place
		if ((sessionStorage.lastPlace && sessionStorage.lastPlace != current_place)) {
			$("#undo").removeClass('hidden-imp')
		}
		// set pass dropdown as next set with any reviewed=False rows
		$("#select_pass").val("{{ passnum }}")
	
		z = window.location.href
		$('#passnum_dynamic').html('<b>' + z.slice(-6) + '</b>')
	
		// defaults to string 'None' - no idea why
		$('.textarea').html('')
	
		$(".create-comment-review").each(function() {
			var recpk = $(this).data('id');
			uribase = "/comment/" + recpk
			next = '?next=' + "{% url 'datasets:review' pk=ds_id tid=task_id passnum=passnum %}"
			$(this).modalForm({
				formURL: uribase + next
			});
		});
	
		$(".view-comments").click(function() {
			$("#record_notes").toggle(300)
		})
	
		$("[rel='tooltip']").tooltip();
		

		$(".help-matches").click(function() {
			page = $(this).data('id')
			$('.selector').dialog('open');
		})
		$(".selector").dialog({
			resizable: true,
			autoOpen: false,
			width: $(window).width() * 0.8,
			height: $(window).height() * 0.9,
			title: "WHG Help",
			modal: true,
			buttons: {
				'Close': function() {
					$(this).dialog('close');
				}
			},
			open: function(event, ui) {
				$('.selector').load('/media/help/' + page + '.html');
			},
			show: {
				effect: "fade",
				duration: 400
			},
			hide: {
				effect: "fade",
				duration: 400
			}
		});
		
		$('.ext').on('click', function(e) {
			e.preventDefault();
			str = $(this).text()
			var re = /(http|bnf|cerl|dbp|gn|gnd|gov|loc|pl|tgn|viaf|wd|wdlocal|whg|wp):(.*?)$/;
			url = str.match(re)[1] == 'http' ? str : base_urls[str.match(re)[1]] + str.match(re)[2]
			console.log('str, url', str, url)
			window.open(url, '_blank')
		});
		// recon authority external links (wd, tgn)
		$('.ext-recon').on('click', function(e) {
			e.preventDefault();
			id = $(this).text()
			url = base_urls[$(this).data('auth')] + id.toString()
			//console.log('id, url',id,url)
			window.open(url, '_blank')
		});
		
		var ds = "{{ ds_label }}" + ':'
		$("#btn_save").click(function() {
			current_place = $('input[name=place_id]').val()
			sessionStorage.setItem('reviewBegun', true)
			// update lastPlace pid in sessionStorage on every save
			sessionStorage.setItem('lastPlace', current_place)
		})
		
		$("#undo").click(function(e) {
			e.preventDefault()
			url = $(this).data('url').replace('999', sessionStorage.lastPlace)
			console.log('undo url:', url)
			document.location.href = url
		});		

		$("#select_pass").change(function() {
			z = window.location.href
			baseurl = z.substring(0, z.lastIndexOf('/') + 1)
			window.location.href = baseurl + $(this).val()
		});
		
		$('.noteicon').on('click', function() {
			$(this).parents(".matchbar").find(".notefield").toggle()
		})
		
		$('.noteicon').hover(function() {
			console.log('hovering')
		})		
		
    })
    .catch(error => console.error("An error occurred:", error));

/*

$(".geolink").hover(function() {
		//console.log($(this))
		let id = $(this)[0].id
		//console.log('id:',id)
		feat = idToFeature[id]
		ogcolor = feat.options.fillColor
		feat.setStyle({
			radius: 10,
			fillColor: 'yellow',
			color: 'red'
		})
	},
	function() {
		let id = $(this)[0].id
		feat = idToFeature[id]
		feat.setStyle({
			radius: 8,
			fillColor: ogcolor,
			color: '#333'
		})
	}
);

// closer look
function zoomTo(id) {
	console.log('zoomTo', id)
	mappy.setView(idToFeature[id]._latlng, mappy.getZoom() + 2)
}

cleanJson = function(text) {
	z = text.replace(/'/g, '\\"')
	y = z.replace(/point/, 'Point')
	return JSON.parse(JSON.parse(y))
}

// initialize, render map
// authority geom "geoms": [{"type": "point", "coordinates": [-72.8667, -13.6167]}]
function map_init(map, options) {
	// console.log('in map_init()')
	window.geom = {
		"type": "FeatureCollecton",
		"features": []
	}

	window.gelems = $('script').filter(function() {
		// return this.id.match(/[0-9]/) && this.text != '"null"';-->
		return this.id != '' && this.text != '"null"';
	});
	//console.log(gelems)
	for (i = 0; i < gelems.length; i++) {
		let t_geom = cleanJson(gelems[i].text)
		t_geom['properties'] = {
			"id": gelems[i].id,
			"ds": t_geom.ds != null ? t_geom.ds : ds
		}
		//citation does not always have id
		      if ('citation' in t_geom){
		        t_geom['properties'] = {"id":t_geom['citation']['id'] }
		      } else t_geom['properties'] = {"id": gelems[i].id,"ds": t_geom.ds!=null?t_geom.ds:ds}
		geom['features'].push(t_geom)
	}

	function fill(ds) {
		//console.log('ds',ds)
		if (['tgn', 'wd', 'whg'].indexOf(ds) >= 0) {
			return "orange"
		} else {
			return "green"
		}
	}

	if (geom['features'].length > 0) {
		//console.log('geom: ',geom)
		idToFeature = {} // for feature lookup
		features = L.geoJSON(geom, {
			pointToLayer: function(feature, latlng) {
				//console.log('feature.properties',feature.properties)
				//console.log('feature',feature)
				matchid = feature.properties.id
				marker = L.circleMarker(latlng, {
					radius: 8,
					fillOpacity: 0.4,
					opacity: 1,
					weight: 1,
					color: "#333",
					fillColor: fill(feature.properties.ds)
				}).bindPopup(matchid);
				marker.on('click', function() {
					console.log('clicked marker w/id', feature.properties.id)
					// .matchbar background change, scroll to it
					// first, background to #fff for all 
					$('.match_radio').css('background', 'oldlace')
					divy = $('.match_radio[data-id=' + feature.properties.id + ']')
					divy.css('background', 'yellow')
					console.log('divy top', divy.position().top)
					$("#review_list").scrollTop(divy.position().top - 80)
					// $('[data-id=' + 'Q1630019' + ']')
				})
				idToFeature[matchid] = marker
				return marker
			}
		}).addTo(map);

		//mappy.setView(features.getBounds().getCenter(),6)
		mappy.fitBounds(features.getBounds())
		mappy.setZoom(mappy.getZoom() - 1)
		mappy.on('popupclose', function() {
			$('.match_radio').css('background', 'oldlace')
			$("#review_list").scrollTop(0)
		})
	} else {
		console.log('no geometries, no feature')
	}
} // end map_init
*/