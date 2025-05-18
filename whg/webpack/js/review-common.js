
import { base_urls } from './aliases.js';

let whg_map = null; // Initialize as null
const mapElement = document.getElementById('map');
if (mapElement) {
    whg_map = new whg_maplibre.Map({
        container: 'map', // Specify the container ID here
        maxZoom: 14,
        style: [
            'WHG',
            'Satellite'
        ],
        scaleControl: true,
    });
} else {
    console.warn("Map container element with id 'map' not found.");
}
export { whg_map };

let featureCollection;

export let layersets = {};

export function initialiseMap() {
	console.log('Map loaded.');	
	
	featureCollection = JSON.parse(featureCollectionJSON);
	console.log(featureCollection);

    // Group features by their 'ds' property
    let groupedFeatures = {};
    featureCollection.features.forEach(feature => {
        const ds = feature.properties.ds;
        if (!groupedFeatures[ds]) {
            groupedFeatures[ds] = [];
        }
        groupedFeatures[ds].push(feature);
    });
    
    if (page_variant == 'reconciliation') {

	    // Create a source and layerset for each group of features based on their 'ds' property
	    const markerColours = {
			'dataset': 'green',
			'wikidata': 'orange',
			'geonames': 'blue',
		} 
	    Object.entries(groupedFeatures).forEach(([ds, features]) => {
	        layersets[ds] = whg_map
	        	.newSource(ds, { type: 'FeatureCollection', features })
	            .newLayerset(ds, null, 'plain', markerColours[ds] || 'brown', ds == 'dataset' ? 'green' : null, ds !== 'dataset', ds == 'dataset' ? 1.3 : 1); // No numbering for `dataset` source marker
	        if (ds=='geonames' && !!groupedFeatures['wikidata']) layersets[ds].toggleVisibility(false);
	    });
		
	}
	else { // page_variant == 'accession'

	    // Create a source and layerset for each group of features based on their 'ds' property
	    const markerColours = {
			'dataset': 'green',
		} 
	    Object.entries(groupedFeatures).forEach(([ds, features]) => {
	        layersets[ds] = whg_map
	        	.newSource(ds, { type: 'FeatureCollection', features })
	            .newLayerset(ds, null, 'plain', markerColours[ds] || 'orange', ds == 'dataset' ? 'green' : null, false, ds == 'dataset' ? 1.3 : 1);
	    });
		
	}
    
    console.log(groupedFeatures, layersets);
	
	if (featureCollection.features.length > 0) {
		whg_map.fitViewport( bbox( featureCollection ), defaultZoom );
	}
	else {
		console.log('No features to map.')
	}
	
	whg_map.getContainer().style.opacity = 1;
}

export function addReviewListeners() {
	
	let current_place = $('input[name=place_id]').val()
	console.log('lastPlace:', sessionStorage.lastPlace)
	console.log('current place:', $('input[name=place_id]').val())
	// show undo link if there is a lastPlace & it's not the current place
	if ((sessionStorage.lastPlace && sessionStorage.lastPlace != current_place)) {
		$("#undo").removeClass('hidden-imp')
	}
	
	let z = window.location.href
	$('#passnum_dynamic').html('<b>' + z.slice(-6) + '</b>');
				
	whg_map.on('click', function(e) { // Find match for map marker
		$('.highlight-row').removeClass('highlight-row');
		const features = whg_map.queryRenderedFeatures(e.point);
		if (features.length > 0) {
			features.forEach(feature => {
				const isAddedFeature = !whg_map.baseStyle.layers.includes(feature.layer.id);
				if (isAddedFeature && !!feature.id) {
					$('.hovermap').eq(feature.id - 1)
					.addClass('highlight-row')
					.closest('.review-item').scrollintoview();
				}
			});
		}
	});	
			
	whg_map.on('mousemove', function(e) { // Change cursor to pointer over map markers
		const features = whg_map.queryRenderedFeatures(e.point);
		function clearHighlight() {
			whg_map.getCanvas().style.cursor = 'grab';
			$('.highlight-row').removeClass('highlight-row');
		}
		if (features.length > 0) {
			const topFeature = features[0]; // Handle only the top-most feature
			const isAddedFeature = !whg_map.baseStyle.layers.includes(topFeature.layer.id);
			if (isAddedFeature && !!topFeature.properties.id) {
				whg_map.getCanvas().style.cursor = 'pointer';
				$('.hovermap').eq(topFeature.id - 1)
				.addClass('highlight-row')
				.closest('.review-item').scrollintoview();
			}
			else clearHighlight();
		}
		else clearHighlight();
	});

	function findMatchingFeature(element) {
		let matchingFeature = featureCollection.features.find(feature => {
			let props = feature.properties;
			return (props.record_id || props.id) === $(element).data('id');
		});
		return matchingFeature;
	}
	
	$(".geolink")
		.attr('title', 'Click to zoom to this location.')
		.on('click', function(){
			let matchingFeature = findMatchingFeature(this);
			whg_map.fitViewport( bbox(matchingFeature), defaultZoom );
		});
	
	$(".hovermap").hover(
	    function() { toggleHighlight(true, this); },
	    function() { toggleHighlight(false, this); }
	);
	
	function toggleHighlight(highlight, element) {
		let matchingFeature = findMatchingFeature(element);
	    if (matchingFeature) {
	        whg_map.setFeatureState({ source: $(element).data('authority'), id: matchingFeature.id }, { highlight });
	        if (whg_map.getSource('dataset')) {
	            whg_map.setFeatureState({ source: 'dataset', id: 0 }, { highlight });
	        }
	    }
	}
	
	// set pass dropdown as next set with any reviewed=False rows
	// $("#select_pass").val(passnum);
	
	// defaults to string 'None' - no idea why
	$('.textarea').html('')
	
	$('.ext').on('click', function(e) {
		e.preventDefault();
		let str = $(this).text().trim();
		var re = /(http|bnf|cerl|dbp|gn|gnd|gov|loc|pl|tgn|viaf|wd|wdlocal|whg|wp):(.*?)$/;
		let url = str.match(re)[1] == 'http' ? str : base_urls[str.match(re)[1]] + str.match(re)[2]
		console.log('str, url', str, url)
		window.open(url, '_blank')
	});

	// recon authority external links (wd, tgn)
	$('.ext-recon').on('click', function(e) {
		e.preventDefault();
		let id = $.trim($(this).text());
		let url = base_urls[$(this).data('auth')] + id.toString()
		console.log('id, url',id,url)
		window.open(url, '_blank')
	});
	
	$("#btn_save").click(function() {
		let current_place = $('input[name=place_id]').val()
		console.log('current place:', current_place)
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
	
	$('.notes').notes();
}
