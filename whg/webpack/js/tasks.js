// /whg/webpack/tasks.js

import '/webpack/node_modules/@maptiler/sdk/dist/maptiler-sdk.umd.min.js';
import '/webpack/node_modules/@maptiler/sdk/dist/maptiler-sdk.css';
import datasetLayers from './mapLayerStyles';
import { attributionString, geomsGeoJSON } from './utilities';
import { bbox } from './6.5.0_turf.min.js';
import { CustomAttributionControl } from './customMapControls';

import '../css/maplibre-common.css';
import '../css/tasks.css';

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
	navigationControl: true,
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

		let msgs = ["{{ msg_wdlocal.type }}", "{{ msg_whg.type }}"]
		console.log('msgs', msgs)
		if ("{{ msg_wdlocal.type }}" == 'done' && '{{ ds.ds_status }}' != 'updated') {
			$("#r_wdlocal").attr('disabled', true)
			$("#r_whg").prop('checked', 'true')
		}
		let found = msgs.slice(0, 2).some(r => ['none', 'unreviewed', 'inprogress'].includes(r))
	
		if (msgs.slice(0, 2).includes("done") && !found) {
			$("#addtask_lower").addClass("hidden")
		}
	
		// set default 
		$("#r_keep_wd").attr('checked', true)
	
		$("#cancel_taskadd").click(function(e) {
			e.preventDefault();
			window.location.href = "{% url 'datasets:ds_reconcile' ds.id %}"
		})
	
		// help modals
		$(".help-matches").click(function() {
			let page = $(this).data('id')
			console.log('help:', page)
			$('.selector').dialog('open');
		})
		$(".selector").dialog({
			resizable: false,
			autoOpen: false,
			height: 500,
			width: 700,
			title: "WHG Help",
			modal: true,
			buttons: {
				'Close': function() {
					console.log('close dialog');
					$(this).dialog('close');
				}
			},
			open: function(event, ui) {
				$('#helpme').load('/media/help/' + page + '.html')
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

		// modal buttons
		$("#btn_done").on('click', function() {
			location.reload();
		})
		$("#btn_cancel").on('click', function() {
			location.reload();
		})
		
		$('#recon_form').change(function() {
			let task = $("input[name='recon']:checked").val();
			if (task == 't_whg') {
				$("#data_limiter").show()
			} else {
				$("#data_limiter").hide()
			}
		});
		
		$('#data_limiter').change(function() {
			let coll = $("#select_colls").val();
			let ds = $("#select_ds").val();
			//huh = $(this)
			//console.log('$(this)', $(this))
			//console.log('coll, ds', coll, ds)
		})

		window.limiter = []
		// clear data limiter dropdown choice if other is used
		$("#select_colls").change(function() {
			$("#select_ds option[value=0]").prop('selected', true)
			limiter = ['c', $(this).val()]
			console.log('limiter:', limiter)
		});
		
		$("#select_ds").change(function() {
			$("#select_colls option[value=0]").prop('selected', true)
			limiter = ['d', $(this).val()]
			console.log('limiter:', limiter)
		});
		
		// clear dropdown choice if other is used & render geometry
		$("#select_region").change(function() {
			$("#select_userarea option[value=0]").prop('selected', true)
			if ($(this).val() == 0) {
				reset_map()
			} else {
				render_area($(this).val(), 'region')
			}
		});
		
		$("#select_userarea").change(function() {
			$("#select_region option[value=0]").prop('selected', true)
			if ($(this).val() == 0) {
				reset_map()
			} else {
				render_area($(this).val(), 'area')
			}
			if ($("#select_userarea option[value='create']").prop('selected') == true) {
				location.href = "{% url 'areas:area-create' %}?next={% url 'datasets:ds_recon' ds.id %}"
			}
		});
		
		$("[rel='tooltip']").tooltip();		
 
    })
    .catch(error => console.error("An error occurred:", error));

function renderMap(featureCollection, tab) {
	if (featureCollection.features.length == 0) {
		console.log('no features in renderMap() call')
	} else {
		
		mappy.getSource('places').setData(featureCollection);
		mappy.setFeatureState({ source: 'places', id: 0 }, { highlight: true });
		
		/* TODO: Not yet implemented in MapLibre - in v2 the popups give `undefined` values.		
		// clear existing if any
		if (typeof(features) !== 'undefined') {
			mappy.removeLayer(features)
		}
		idToFeature = {} // for feature lookup
		features = L.geoJSON(featureCollection, {
			// feature here is a geometry
			// TODO: LPF should allow single geometry, not only GeometryCollection
			pointToLayer: function(feature, latlng) {
				matchid = feature.place_id
				//console.log('feature',feature)
				marker = L.circleMarker(latlng, styles.Point.default).bindPopup(feature.title +
					'<br>pid: <a href="' + window.location.origin + '/api/db?id=' + matchid + '" target="_blank">' +
					matchid + '</a>');
				idToFeature[matchid] = marker
				return marker
			},
			onEachFeature: function(feature, layer) {
				f = feature;
				l = layer;
				identifier = f.place_id;
				if (f.type != 'Point') {
					layer.setStyle(styles[f.type].default).bindPopup(
						f.title + '<br>pid: <a href="' +
						window.location.origin + '/api/db?id=' +
						identifier + '" target="_blank">' + identifier + '</a>'
					)
					idToFeature[identifier] = layer
				}
			}
		}).addTo(mappy);
		*/
	}
	mappy.fitBounds(bbox(featureCollection), {
        padding: 30,
        duration: 1000,
    });
}

// area-related
function render_area(aid) {
	$.ajax({
		url: '/api/area/' + aid
	}).done(function(data) {
		data['geom'] = data.geojson;
		delete data.geojson;
		let featureCollection = geomsGeoJSON([data])
		console.log('render_area()', data, featureCollection)
		renderMap(featureCollection, 'area')
		$("#area_name").html(data.title).show()
	})
}

function reset_map() {
	$("#area_name").html('Global');
	mappy.getSource('places').setData(nullCollection);
	mappy.flyTo({
	    center: mapParameters.center,
	    zoom: mapParameters.zoom,
        duration: 1000,
	});
}
