// /whg/webpack/portal.js

import datasetLayers from './mapLayerStyles';
import { attributionString, geomsGeoJSON } from './utilities';
import { bbox } from './6.5.0_turf.min.js';
import { CustomAttributionControl } from './customMapControls';
import Dateline from './dateline';

import '../css/maplibre-common.css';
import '../css/mapAndTableMirrored.css';
import '../css/dateline.css';
import '../css/portal.css';

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
	userProperties: true
});

let nullCollection = {
    type: 'FeatureCollection',
    features: []
}

function waitMapLoad() {
    return new Promise((resolve) => {
        mappy.on('load', () => {
            console.log('Map loaded.');
			const whgMap = document.getElementById(mapParameters.container);
            
			const controlContainer = document.querySelector('.maplibregl-control-container');
			controlContainer.setAttribute('id', 'mapControls');
			controlContainer.classList.add('item');
		
			const mapOverlays = document.createElement('div');
			mapOverlays.id = 'mapOverlays';
			whgMap.appendChild(mapOverlays);
		
			['left', 'right'].forEach(function(side) {
				const column = document.createElement('div');
				column.classList.add('column', side);
				mapOverlays.appendChild(column);
				const overlays = document.querySelectorAll('.overlay.' + side);
				overlays.forEach(function(overlay) {
					if (overlay.id == 'map') {
						column.appendChild(controlContainer);	
						overlay.classList.remove('overlay','left','right');					
					}
					else {
						column.appendChild(overlay);
						overlay.classList.add('item');
					}
				})
			})
            
            mappy.addSource('places', {
				'type': 'geojson',
			    'data': nullCollection,
				'attribution': attributionString(),
			});
		    datasetLayers.forEach(function(layer) {
				mappy.addLayer(layer);
			});
			
			mappy.addControl(new CustomAttributionControl({
				compact: true,
		    	autoClose: mapParameters.controls.attribution.open === false,
			}), 'bottom-right');

			function dateRangeChanged(fromValue, toValue){
				let debounceTimeout;
			    function debounceFilterApplication() {
			        clearTimeout(debounceTimeout);
			        //debounceTimeout = setTimeout(toggleFilters(true, mappy, table), 300);
			    }
			    debounceFilterApplication();
			}

			if (!!mapParameters.controls.temporal) {
				let datelineContainer = document.createElement('div');
				datelineContainer.id = 'dateline';
				document.getElementById('mapControls').appendChild(datelineContainer);		
				window.dateline = new Dateline({
					...mapParameters.controls.temporal,
					onChange: dateRangeChanged
				});
			};
			
			// TODO: Add basemap style-switcher?
			// TODO: Configure resize observer for map padding initialisation and updates
			
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
		
	  	const payload = JSON.parse(document.getElementById('payload_data').textContent);
	  	console.log('payload', payload);
			
		let featureCollection = geomsGeoJSON(payload);
		console.log(featureCollection);
		mappy.getSource('places').setData(featureCollection);
		mappy.fitBounds(bbox(featureCollection), {
	        padding: 30,
	        duration: 1000,
	    });
	  	
	  	var min = Math.min.apply(null, allts.map(function(row) {
	  		return Math.min.apply(Math, row);
	  	}));
	  	var max = Math.max.apply(null, allts.map(function(row) {
	  		return Math.max.apply(Math, row);
	  	}));
	  	let minmax = [min, max]
	  	// feed to #histogram
	  	histogram_data(allts, minmax)

	  	// load collection geometry (# within reason)
	  	$(".coll-geo").click(function(e) {
	  		e.preventDefault()
	  		// TODO: why does context fail when collection places are displayed
	  		// in any case, hide the checkbox
	  		$("#fetch_context").hide()
	  		fetchCollectionGeom($(this).data('id'), 3)
	  		$("#clear_markers").fadeIn()
	  	})
	  	
    })
    .catch(error => console.error("An error occurred:", error));

function range(start, stop, step) {
	var a = [start],
		b = start;
	while (b < stop) {
		a.push(b += step || 1);
	}
	return a;
}

function intersects(a, b) {
	let min = (a[0] < b[0] ? a : b)
	let max = (min == a ? b : a)
	return !(min[1] < max[1])
}

function histogram_data(intervals, minmax) {
	let step = Number(((minmax[1] - minmax[0]) / 200))
	let bins = range(minmax[0], minmax[1], step)
	let hist_array = Array.apply(null, Array(bins.length)).map(Number.prototype.valueOf, 0);
	let labels = bins.map(function(d) {
		return Math.round(d)
	})
	for (var b = 0; b < bins.length; b++) {
		let bin = Array(bins[b], bins[b + 1])
		for (var i in intervals) {
			if (intersects(bin, intervals[i])) {
				hist_array[b] += 1
			}
		}
	}
	let data = hist_array.map(function(d, i) {
		return {
			"bin": labels[i],
			"count": d
		}
	})

	// visualize it
	histogram(data, labels, minmax)

}

function histogram(data, labels, minmax) {
	// exit if no data
	if (data[0].bin == "Infinity") {
		$("#histogram").html('<i>None yet</i>');
		return;
	}
	data = data.slice(0, 200)
	let curwidth = $("#histogram").width()

	var margin = {
			top: 0,
			right: 10,
			bottom: 0,
			left: 10
		},
		width = 400,
		height = 30,
		padding_h = 20,
		padding_w = 30;

	// set the ranges
	window.xScale = d3.scaleLinear()
		.range([0, width])
	window.yScale = d3.scaleLinear()
		.range([height, 0]);

	xScale.domain(minmax);
	yScale.domain([0, d3.max(data, function(d) {
		return d.count;
	})]);

	// TODO: responsive scaling of svg width
	window.svg_hist = d3.select("#histogram").append("svg")
		.attr("width", '100%')
		.attr("height", height + padding_h)

		.attr('viewBox', '0 0 ' + Math.min(width, height + padding_h) + ' ' + Math.min(width, height + padding_h))
		.attr('preserveAspectRatio', 'xMinYMin')

		.append("g")
		.attr("transform", "translate(" + margin.left + "," + margin.top + ")")

	window.axisB = d3.axisBottom(xScale)
		.tickValues(labels.filter(function(d, i) {
			return !(i % 20)
		}))
		.tickFormat(d3.format("d"));

	var axisL = d3.axisLeft(yScale)

	svg_hist.selectAll(".bar")
		.data(data)
		.enter().append("rect")
		.attr("class", "bar")
		.attr("x", function(d) {
			return xScale(d.bin);
		})
		//.attr("width", function(d) { return xScale(d.x1) - xScale(d.x0) -1 ; })
		.attr("width", 2)
		.attr("y", function(d) {
			return yScale(d.count);
		})
		.attr("height", function(d) {
			return height - yScale(d.count);
		});

	var xAxis = svg_hist.append("g")
		.attr("id", "xaxis")
		.attr("transform", "translate(0," + height + ")")
		.call(axisB)
}  

function fetchCollectionGeom(coll_id, counter) {
  	counter = 3
  	$.get("/search/collgeom", {
  			coll_id: coll_id
  		},
  		function(data) {
  			coll_places = data
  			console.log('coll_places', coll_places)
  		});
}