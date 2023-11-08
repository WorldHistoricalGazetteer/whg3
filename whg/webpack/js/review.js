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

function waitMapLoad() {
    return new Promise((resolve) => {
        mappy.on('load', () => {
            console.log('Map loaded.');
			const whgMap = document.getElementById(mapParameters.container);
			
			if (mapParameters.styleFilter.length !== 1) {
				styleControl = new acmeStyleControl(mappy);
				mappy.addControl(styleControl, 'top-right');
			}		
			
			featureCollection = JSON.parse(featureCollectionJSON);
			console.log(featureCollection);
            
            mappy.addSource('places', {
				'type': 'geojson',
			    'data': featureCollection,
				'attribution': attributionString(),
			});
		    datasetLayers.forEach(layer => {
				mappy.addLayer(layer);
			});
			
			if (featureCollection.features.length > 0) {
				mappy.fitViewport( bbox( featureCollection ) );
			}
			else {
				console.log('No features to map.')
			}
			
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
				
		mappy.on('click', function(e) { // Find match for map marker
			const features = mappy.queryRenderedFeatures(e.point);
			if (features.length > 0) {
				const topFeature = features[0]; // Handle only the top-most feature
				const isAddedFeature = !styleControl.baseStyle.layers.includes(topFeature.layer.id);
				if (isAddedFeature && !!topFeature.properties.src_id) {
					$('.match_radio').css('background', 'oldlace'); // first, background to #fff for all 
					const divy = $('.match_radio[data-id=' + topFeature.properties.src_id + ']');
					divy.css('background', 'yellow'); // .matchbar background change, scroll to it
					console.log(`Clicked marker: ${ topFeature.properties.src_id }; Matched div top: ${ divy.position().top }`);
					$("#review_list").scrollTop(divy.position().top - 80);
				}
			}
		});	
				
		mappy.on('mousemove', function(e) { // Change cursor to pointer over map markers
			const features = mappy.queryRenderedFeatures(e.point);
			if (features.length > 0) {
				const topFeature = features[0]; // Handle only the top-most feature
				const isAddedFeature = !styleControl.baseStyle.layers.includes(topFeature.layer.id);
				if (isAddedFeature && !!topFeature.properties.src_id) {
					mappy.getCanvas().style.cursor = 'pointer';
				}
				else {
					mappy.getCanvas().style.cursor = 'grab';
				}
			}
			else {
				mappy.getCanvas().style.cursor = 'grab';
			}
		});	
		
		$(".match_radio").hover(
		    function() { toggleHighlight(true, this); },
		    function() { toggleHighlight(false, this); }
		);
		
		function toggleHighlight(highlight, element) {
		    let targetId = $(element).data('id');
		    let matchingFeature = featureCollection.features.find(feature => feature.properties.src_id === targetId);
		    if (matchingFeature) {
		        mappy.setFeatureState({ source: 'places', id: matchingFeature.id }, { highlight });
		    }
		}

		console.log(`already: ${ already }`)
		if (already !=='') {
			alert('last record was saved by someone else, this is the next')
		}
		let current_place = $('input[name=place_id]').val()
		console.log('lastPlace:', sessionStorage.lastPlace)
		console.log('current place:', $('input[name=place_id]').val())
		// show undo link if there is a lastPlace & it's not the current place
		if ((sessionStorage.lastPlace && sessionStorage.lastPlace != current_place)) {
			$("#undo").removeClass('hidden-imp')
		}
		// set pass dropdown as next set with any reviewed=False rows
		$("#select_pass").val(passnum)
	
		let z = window.location.href
		$('#passnum_dynamic').html('<b>' + z.slice(-6) + '</b>')
	
		// defaults to string 'None' - no idea why
		$('.textarea').html('')
	
		$(".create-comment-review").each(function() {
			var recpk = $(this).data('id');
			let uribase = "/comment/" + recpk
			let next = '?next=' + "{% url 'datasets:review' pk=ds_id tid=task_id passnum=passnum %}"
			$(this).modalForm({
				formURL: uribase + next
			});
		});
	
		$(".view-comments").click(function() {
			$("#record_notes").toggle(300)
		})
	
		$("[rel='tooltip']").tooltip();
		

		$(".help-matches").click(function() {
			let page = $(this).data('id')
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
			let str = $(this).text()
			var re = /(http|bnf|cerl|dbp|gn|gnd|gov|loc|pl|tgn|viaf|wd|wdlocal|whg|wp):(.*?)$/;
			let url = str.match(re)[1] == 'http' ? str : base_urls[str.match(re)[1]] + str.match(re)[2]
			console.log('str, url', str, url)
			window.open(url, '_blank')
		});
		// recon authority external links (wd, tgn)
		$('.ext-recon').on('click', function(e) {
			e.preventDefault();
			let id = $(this).text()
			let url = base_urls[$(this).data('auth')] + id.toString()
			//console.log('id, url',id,url)
			window.open(url, '_blank')
		});
		
		var ds = ds_label + ':' // TODO: This appears to be redundant
		
		$("#btn_save").click(function() {
			let current_place = $('input[name=place_id]').val()
			sessionStorage.setItem('reviewBegun', true)
			// update lastPlace pid in sessionStorage on every save
			sessionStorage.setItem('lastPlace', current_place)
		})
		
		$("#undo").click(function(e) {
			e.preventDefault()
			let url = $(this).data('url').replace('999', sessionStorage.lastPlace)
			console.log('undo url:', url)
			document.location.href = url
		});		

		$("#select_pass").change(function() {
			let z = window.location.href
			let baseurl = z.substring(0, z.lastIndexOf('/') + 1)
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
