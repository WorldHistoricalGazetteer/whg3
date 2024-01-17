
import datasetLayers from './mapLayerStyles';
import { attributionString } from './utilities';

export let mappy = new whg_maplibre.Map({
	maxZoom: 10
});

let featureCollection;

export function initialiseMap() {
	console.log('Map loaded.');	
	
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
	
	mappy.getContainer().style.opacity = 1;
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
				
	mappy.on('click', function(e) { // Find match for map marker
		const features = mappy.queryRenderedFeatures(e.point);
		if (features.length > 0) {
			let scrolled = false;
			features.forEach(feature => {
				const isAddedFeature = !mappy.baseStyle.layers.includes(feature.layer.id);
				if (isAddedFeature && !!feature.properties.src_id) {
					if (!scrolled) {
						$('.match_radio').css('background', 'oldlace'); // first, background to #fff for all 
					}
					const divy = $('.match_radio[data-id=' + feature.properties.src_id + ']');
					divy.css('background', 'yellow'); // .matchbar background change, scroll to it
					console.log(`Clicked marker: ${ feature.properties.src_id }`);
					if (!scrolled) {
						console.log(`First matched div top: ${ divy.position().top }`);
						$("#review_list").scrollTop(divy.position().top - 80);
						scrolled = true;
					}
				}
			});
		}
	});	
			
	mappy.on('mousemove', function(e) { // Change cursor to pointer over map markers
		const features = mappy.queryRenderedFeatures(e.point);
		function clearHighlight() {
			mappy.getCanvas().style.cursor = 'grab';
			$('.highlight-row').removeClass('highlight-row');
		}
		if (features.length > 0) {
			const topFeature = features[0]; // Handle only the top-most feature
			const isAddedFeature = !mappy.baseStyle.layers.includes(topFeature.layer.id);
			if (isAddedFeature && !!topFeature.properties.id) {
				mappy.getCanvas().style.cursor = 'pointer';
				$(`.hovermap[data-id='${ topFeature.properties.id }']`).addClass('highlight-row');
			}
			else clearHighlight();
		}
		else clearHighlight();
	});
	
	$(".geolink")
		.attr('title', 'Click to zoom to this location.')
		.on('click', function(){
			mappy.fitViewport( bbox(featureCollection.features.find(feature => feature.properties.id === $(this).data('id'))) );
		});
	
	$(".hovermap").hover(
	    function() { toggleHighlight(true, this); },
	    function() { toggleHighlight(false, this); }
	);
	
	function toggleHighlight(highlight, element) {
	    let matchingFeature = featureCollection.features.find(feature => feature.properties.id === $(element).data('id'));
	    if (matchingFeature) {
	        mappy.setFeatureState({ source: 'places', id: matchingFeature.id }, { highlight });
	    }
	}		
	
	$(".create-comment-review").each(function() {
		var recpk = $(this).data('id');
		let uribase = "/comment/" + recpk
		let next = '?next=' + "{% url 'datasets:review' pk=ds_id tid=task_id passnum=passnum %}"
		$(this).modalForm({
			formURL: uribase + next
		});
	});

	$(".help-matches, .help").click(function() {
		let page = $(this).data('id')
		$('.selector').dialog('open');
	})
	
	$("[rel='tooltip']").tooltip();
	
	// set pass dropdown as next set with any reviewed=False rows
	$("#select_pass").val(passnum);
	
	// defaults to string 'None' - no idea why
	$('.textarea').html('')
	
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
}
