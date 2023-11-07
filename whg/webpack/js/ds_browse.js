// /whg/webpack/js/ds_browse.js

import './extend-maptiler-sdk.js'; // Adds 'fitViewport' method
import datasetLayers from './mapLayerStyles';
import { bbox } from './6.5.0_turf.min.js';
import { attributionString, startSpinner } from './utilities';
import { acmeStyleControl, CustomAttributionControl } from './customMapControls';
import { getPlace } from './getPlace';

import '../css/maplibre-common.css';
import '../css/style-control.css';
import '../css/ds_browse.css';

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

let featureCollection;
let nullCollection = {
    type: 'FeatureCollection',
    features: []
}
let highlightedFeatureId = false;

let table;

function waitMapLoad() {
    return new Promise((resolve) => {
        mappy.on('load', () => {
            console.log('Map loaded.');
			const whgMap = document.getElementById(mapParameters.container);
			let hilited = null;
			
			if (mapParameters.styleFilter.length !== 1) {
				mappy.addControl(new acmeStyleControl(mappy), 'top-right');
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
			
			renderData(ds_id)
			
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
		
		console.log(`wdtask: ${wdtask}, tgntask: ${tgntask}, whgtask: ${whgtask}, anytask: ${anytask}`);
	  	
		localStorage.setItem('filter', '99')
		// hide filter dropdown if there are no tasks
		const filter_col = anytask ? "<'#status_filter.col-sm-12 col-md-5'>" : "<'#nostatus.col-sm-12 col-md-5'>";
		
		buildSelect();
		const spinner_table = startSpinner("drftable_list");
		
		table = $('#placetable').DataTable({
			dom: "<'row'<'col-sm-12 col-md-3'l>+" +
				filter_col +
				"<'col-sm-12 col-md-4'f>>" +
				"<'row'<'col-sm-12'tr>>" +
				"<'row'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>",
			serverSide: true,
			ajax: {
				url: `/api/placetable/?format=datatables&ds=${dslabel}`
			},
			scrollY: 400,
			select: true,
			order: [
				[2, 'asc']
			],
			columns: [{
					"data": "id"
				},
				{
					"data": "src_id"
				},
				{
					"data": "title"
				},
				{
					"data": "ccodes"
				},
				{
					"data": "geo"
				},
				{
					"data": "review_wd"
				},
				{
					"data": "review_tgn"
				},
				{
					"data": "review_whg"
				},
				{
					"data": "revwd",
					"visible": wdtask ? true : false,
					"orderable": false
				},
				{
					"data": "revtgn",
					"visible": tgntask ? true : false,
					"orderable": false
				},
				{
					"data": "revwhg",
					"visible": whgtask ? true : false,
					"orderable": false
				}
			],
			columnDefs: [{
					className: "browse-task-col",
					"targets": [8, 9, 10]
				},
				{
					orderable: false,
					"targets": [4, 5, 6, 7]
				},
				{
					searchable: false,
					"targets": [0, 1, 3, 4, 8, 9, 10]
				}, {
					visible: false,
					"targets": [5, 6, 7]
				}
			],
			initComplete: function(settings, json) {
			},
			drawCallback: function(settings) {
				$("#status_filter").html(buildSelect());
				$("#status_select").val(localStorage.getItem('filter'))
				spinner_table.stop()
				setRowEvents();
			}
			
		})
		
    })
    .catch(error => console.error("An error occurred:", error));
    

function setRowEvents() {
	$("#status_select").change(function(e) {
		// clear search first
		console.log('search has val:', $("#placetable_filter input").val())
		//$("#placetable_filter input").val('')
		if ($("#placetable_filter input").val() != '') {
			$('#placetable').DataTable().search('').draw()
		}
		//fnDraw()
		const val = $(this).val();
		localStorage.setItem('filter', val);
		console.log(val);
		const spinner_filter = startSpinner("status_filter");
		if (val == '99') {
			// clear search
			clearFilters();
		} else {
			clearFilters();
			filterColumn(val[0], val[1]);
		}
		spinner_filter.stop();
	})

	$("#placetable tbody tr").click(function() {
		const thisy = $(this);
		// close popup if exists
		if (typeof poppy != 'undefined') {
			poppy.remove();
		}
		// get id
		const pid = parseInt( $(this)[0].cells[0].textContent );
		if ( highlightedFeatureId ) {
			mappy.setFeatureState({ source: 'places', id: highlightedFeatureId }, { highlight: false });
		}
		const feat = featureCollection.features.find(feature => feature.properties.pid === pid);
		if (feat) {
			highlightedFeatureId = feat.id;
			mappy
			.setFeatureState({ source: 'places', id: highlightedFeatureId }, { highlight: true })
			.fitViewport( bbox( feat ) );
		}
		else {
			highlightedFeatureId = false;
		}

		// highlight this row, clear others
		var selected = $(this).hasClass("highlight-row");
		$("#placetable tr").removeClass("highlight-row");

		if (!selected)
			$(this).removeClass("rowhover");
		$(this).addClass("highlight-row");

		// fetch its detail
		getPlace(pid);

	})

	const row = $("#drftable_list table tbody")[0].rows[0];
	const pid = parseInt(row.cells[0].textContent);
	// highlight first row, fetch detail, but don't zoomTo() it
	$("#placetable tbody").find('tr').eq(0).addClass('highlight-row');

	if (pid) {
		const spinner_detail = startSpinner("row_detail");
		getPlace(pid);
		spinner_detail.stop();
	}
}    
    
/*
$(function() {



	// help popups
	$(".help-matches").click(function() {
		page = $(this).data('id')
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
}) /* end onload()

// activate all tooltips
$("[rel='tooltip']").tooltip();

// called by table row click
function highlightFeatureGL(pid, geom, coords) {
	//console.log('pid, coords',pid, coords);
	// TODO: 
	if (geom.type.includes('Point')) {
		// restore full opacity in case it was dimmed
		mappy.setPaintProperty('gl_active_point', 'circle-opacity', 1.0);
		mappy.setPaintProperty(
			'gl_active_point', 'circle-radius', {
				'property': 'pid',
				'type': 'categorical',
				'default': 3,
				'stops': [
					[Number(pid), 8]
				]
			}
		);
		mappy.setPaintProperty(
			'gl_active_point', 'circle-stroke-color', {
				'property': 'pid',
				'type': 'categorical',
				'stops': [
					[Number(pid), '#666']
				]
			}
		);
		mappy.setPaintProperty(
			'gl_active_point', 'circle-stroke-width', {
				'property': 'pid',
				'type': 'categorical',
				'stops': [
					[Number(pid), 1]
				]
			}
		);
		mappy.setPaintProperty(
			'gl_active_point', 'circle-color', {
				'property': 'pid',
				'default': '#ff9900',
				'type': 'categorical',
				'stops': [
					[Number(pid), 'red']
				]
			}
		);
	} else if (geom.type.includes('Polygon')) {
		// fade points when polygon is highlighted
		mappy.setPaintProperty('gl_active_point', 'circle-opacity', 0.4);
		mappy.setPaintProperty(
			'gl_active_poly', 'fill-outline-color', {
				'property': 'pid',
				'default': 'grey',
				'type': 'categorical',
				'stops': [
					[Number(pid), 'red']
				]
			}
		);
		mappy.setPaintProperty(
			'gl_active_poly', 'fill-color', {
				'property': 'pid',
				'default': "rgba(255,0,0, 0.4)",
				// 'default': "rgba(255,255,255,0.0)",
				'type': 'categorical',
				// 'type':'categorical',
				'stops': [
					[Number(pid), 'rgba(0,128,0,1.0)']
				]
			}
		);

	} else if (geom.type.includes('Line')) {
		mappy.setPaintProperty(
			'gl_active_line', 'line-color', {
				'property': 'pid',
				'default': "lightblue",
				'type': 'categorical',
				'stops': [
					[Number(pid), 'blue']
				]
			}
		);
		mappy.setPaintProperty(
			'gl_active_line', 'line-width', {
				'property': 'pid',
				'default': 1,
				'type': 'categorical',
				'stops': [
					[Number(pid), 2]
				]
			}
		);
	}

	// zoom to feature
	if (geom.type.toLowerCase() == 'point') {
		flycoords = typeof(coords[0]) == 'number' ? coords : coords[0]
		mappy.flyTo({
			'center': flycoords,
			'zoom': 7
		})
	} else {
		bbox = turf.envelope(geom).bbox
		mappy.fitBounds(bbox, {
			padding: 30
		})
	}

}

function popupMaker(place, lnglat) {
	console.log('lnglat', lnglat)
	// lnglat is clicked point
	var coordinates = [lnglat.lng, lnglat.lat];
	var props = place.properties
	var pid = props.pid;
	var title = props.title;
	var src_id = props.src_id;
	var min = props.min;
	var max = props.max;
	var fc = props.fclasses;

	 Ensure that if the map is zoomed out such that multiple
	   copies of the feature are visible, the popup appears
	   over the copy being pointed to. 
	while (Math.abs(lnglat.lng - coordinates[0]) > 180) {
		coordinates[0] += lnglat.lng > coordinates[0] ? 360 : -360;
	}

	// popup
	var html = '<b>' + title + '</b><br/>' + '<a href="javascript:getPlace(' + pid + ')">fetch info</a>'
	if (min != 'null') {
		html += '<br/>earliest: ' + min + '<br/>' + 'latest: ' + max
	}
	poppy = new maplibregl.Popup()
		.setLngLat(coordinates)
		.setHTML(html)
		.addTo(mappy);
}
// all this for a popup, on ONE layer
// TODO: repeat for lines and polygons
mappy.on('click', 'gl_active_point', function(e) {
	// console.log('e.lngLat', e.lngLat)
	//lng = e.lngLat.lng
	lnglat = e.lngLat
	//lngLat = e.lngLat
	place = e.features[0]
	//console.log('clicked point, lng', place, lng)
	// 
	popupMaker(place, lnglat)
});

mappy.on('click', 'gl_active_line', function(e) {
	lnglat = e.lngLat
	place = e.features[0]
	// console.log('clicked line, lngLat', place, lnglat)
	// 
	popupMaker(place, lnglat)
});

mappy.on('click', 'gl_active_poly', function(e) {
	lnglat = e.lngLat
	place = e.features[0]
	// console.log('clicked line, lngLat', place, lnglat)
	// 
	popupMaker(place, lnglat)
});

// Change the cursor to a pointer when the mouse is over the point layer.
mappy.on('mouseenter', 'gl_active_point', function() {
	mappy.getCanvas().style.cursor = 'pointer';
});
// Change it back to a pointer when it leaves.
mappy.on('mouseleave', 'gl_active_point', function() {
	mappy.getCanvas().style.cursor = '';
});

mappy.on('mouseenter', 'gl_active_line', function() {
	mappy.getCanvas().style.cursor = 'pointer';
});
// Change it back to a pointer when it leaves.
mappy.on('mouseleave', 'gl_active_line', function() {
	mappy.getCanvas().style.cursor = '';
});

mappy.on('mouseenter', 'gl_active_poly', function() {
	mappy.getCanvas().style.cursor = 'pointer';
});
// Change it back to a pointer when it leaves.
mappy.on('mouseleave', 'gl_active_poly', function() {
	mappy.getCanvas().style.cursor = '';
});

// generic 
function zoomTo(pid) {
	console.log('zoomTo()', pid)
	l = idToFeature[pid]
	ftype = l.feature.geometry.type
	//console.log('zoomTo() pid, ftype',pid, ftype)
	if (ftype == 'Point') {
		mappy.setView(l._latlng, 7)
	} else {
		mappy.fitBounds(l.getBounds(), {
			padding: [100, 100]
		})
	}
}


// builds link for external place record
function url_extplace(identifier) {
	// abbreviate links not in aliases.base_urls
	if (identifier.startsWith('http')) {
		let tag = identifier.replace(/.+\/\/|www.|\..+/g, '')
		link = '<a href="' + identifier + '" target="_blank">' + tag + ' <i class="fas fa-external-link-alt linky"></i>, </a>'
	} else {
		link = '<a href="" class="ext" data-target="#ext_site">' + identifier + ' <i class="fas fa-external-link-alt linky"></i></a>, '
	}
	return link
}

// builds link for external placetype record
function url_exttype(type) {
	link = ' <a href="#" class="exttab" data-id=' + type.identifier +
		'>(' + type.label + ' <i class="fas fa-external-link-alt linky"></i>)</a>'
	return link
}

function minmaxer(timespans) {
	//console.log('got to minmax()',JSON.stringify(timespans))
	starts = [];
	ends = []
	for (t in timespans) {
		// gets 'in', 'earliest' or 'latest'
		starts.push(Object.values(timespans[t].start)[0])
		ends.push(!!timespans[t].end ? Object.values(timespans[t].end)[0] : -1)
	}
	//console.log('starts',starts,'ends',ends)
	minmax = [Math.max.apply(null, starts), Math.max.apply(null, ends)]
	return minmax
}

// detail for selected place, below map
function parsePlace(data) {
	window.featdata = data

	function onlyUnique(array) {
		const map = new Map();
		const result = [];
		for (const item of array) {
			if (!map.has(item.identifier)) {
				map.set(item.identifier, true);
				result.push({
					identifier: item.identifier,
					type: item.type,
					aug: item.aug
				});
			}
		}
		return (result)
	}
	//timespan_arr = []
	//
	// TITLE 
	descrip = '<p><b>Title</b>: <span id="row_title" class="larger text-danger">' + data.title + '</span>'
	//
	// NAME VARIANTS
	descrip += '<p class="scroll65"><b>Variants</b>: '
	for (n in data.names) {
		let name = data.names[n]
		if (name.toponym != data.title) {
			descrip += '<p>' + name.toponym != '' ? name.toponym + '; ' : ''
		}
	}
	//
	// TYPES
	// may include sourceLabel:"" **OR** sourceLabels[{"label":"","lang":""},...]
	// console.log('data.types',data.types)
	//{"label":"","identifier":"aat:___","sourceLabels":[{"label":" ","lang":"en"}]}
	descrip += '</p><p><b>Types</b>: '
	typeids = ''
	for (t in data.types) {
		str = ''
		var type = data.types[t]
		//console.log('type',type)
		if ('sourceLabels' in type) {
			srclabels = type.sourceLabels
			for (l in srclabels) {
				label = srclabels[l]['label']
				str = label != '' ? label + '; ' : ''
			}
		} else if ('sourceLabel' in type) {
			str = type.sourceLabel != '' ? type.sourceLabel + '; ' : ''
		}
		if (type.label != '') {
			str += url_exttype(type) + ' '
		}
		typeids += str
	}
	descrip += typeids.replace(/(; $)/g, "") + '</p>'

	//
	// LINKS
	// 
	descrip += '<p class="mb-0"><b>Links</b>: <i>original: </i>'
	close_count = added_count = related_count = 0
	html_close = html_added = html_related = ''
	if (data.links.length > 0) {
		links = data.links
		links_arr = onlyUnique(data.links)
		console.log('distinct data.links', links_arr)
		for (l in links_arr) {
			//console.log('link',links_arr[l])
			if (links_arr[l].aug == true) {
				added_count += 1
				html_added += url_extplace(links_arr[l].identifier)
			} else {
				close_count += 1
				html_close += url_extplace(links_arr[l].identifier)
			}
		}
		descrip += close_count > 0 ? html_close : 'none; '
		descrip += added_count > 0 ? '<i>added</i>: ' + html_added : '<i>added</i>: none'
	} else {
		descrip += "<i class='small'>no links established yet</i>"
	}
	descrip += '</p>'

	//
	// RELATED
	//right=''
	if (data.related.length > 0) {
		parent = '<p class="mb-0"><b>Parent(s)</b>: ';
		related = '<p class="mb-0"><b>Related</b>: ';
		for (r in data.related) {
			rel = data.related[r]
			//console.log('rel',rel)
			if (rel.relation_type == 'gvp:broaderPartitive') {
				parent += '<span class="h1em">' + rel.label
				parent += 'when' in rel && !('timespans' in rel.when) ?
					', ' + rel.when.start.in + '-' + rel.when.end.in :
					'when' in rel && ('timespans' in rel.when) ? ', ' +
					minmaxer(rel.when.timespans) : ''
				//rel.when.timespans : ''
				parent += '</span>; '
			} else {
				related += '<p class="small h1em">' + rel.label + ', ' + rel.when.start.in + '-' + rel.when.end.in + '</p>'
			}
		}
		descrip += parent.length > 39 ? parent : ''
		descrip += related.length > 37 ? related : ''
	}
	//
	// DESCRIPTIONS
	// TODO: link description to identifier URI if present
	if (data.descriptions.length > 0) {
		val = data.descriptions[0]['value'].substring(0, 300)
		descrip += '<p><b>Description</b>: ' + (val.startsWith('http') ? '<a href="' + val + '" target="_blank">Link</a>' : val) +
			' ... </p>'
		//'<br/><span class="small red-bold">('+data.descriptions[0]['identifier']+')</span>
	}
	//
	// CCODES
	//
	//if (data.ccodes.length > 0) {
	if (!!data.countries) {
		//console.log('data.countries',data.countries)
		descrip += '<p><b>Modern country bounds</b>: ' + data.countries.join(', ') + '</p>'
	}
	//
	// MINMAX
	//
	//console.log('data.minmax',data.minmax)
	mm = data.minmax
	if (data.minmax && !(mm[0] == null && mm[1] == null)) {
		descrip += '<p><b>When</b>: earliest: ' + data.minmax[0] + '; latest: ' + data.minmax[1]
	}

	// if geom(s) and 'certainty', add it
	if (data.geoms.length > 0) {
		cert = data.geoms[0].certainty
		if (cert != undefined) {
			descrip += '<p><b>Location certainty</b>: ' + cert + '</p>'
		}
	}
	descrip += '</div>'
	return descrip
}

// fetch single complete-ish place record
function getPlace(pid) {
	console.log('getPlace()', pid)
	$.ajax({
		url: "/api/place/" + pid,
		headers: {
			'calling_page': 'ds_browse'
		}
	}).done(function(data) {
		console.log('place data', data)
		$("#detail").html(parsePlace(data))
		spinner_detail.stop()
		// events on detail items
		$('.ext').on('click', function(e) {
			e.preventDefault();
			str = $(this).text()
			//console.log('str (identifier)',str)
			// URL identifiers can be 'http*' or an authority prefix
			if (str.substring(0, 4).toLowerCase() == 'http') {
				url = str
			} else {
				var re = /(http|bnf|cerl|dbp|gn|gnd|gov|loc|pl|tgn|viaf|wd|wdlocal|whg|wp):(.*?)$/;
				url = base_urls[str.match(re)[1]] + str.match(re)[2]
				console.log('getPlace() url', url, encodeURI(url))
			}
			window.open(url, '_blank');
			// window.open(encodeURI(url), '_blank');
		});
		$('.exttab').on('click', function(e) {
			e.preventDefault();
			id = $(this).data('id').toString()
			console.log('id', id)
			var re = /(http|dbp|gn|tgn|wd|loc|viaf|aat):(.*?)$/;
			url = id.match(re)[1] == 'http' ? id : base_urls[id.match(re)[1]] + id.match(re)[2]
			console.log('url', url)
			window.open(url, '_blank')
		});
	});
	//spinner_detail.stop()
}
*/


// fetch and render
function renderData(dsid) {
        		
    fetch(`/datasets/${ dsid }/geojson`)
        .then((response) => {
            if (!response.ok) {
                throw new Error('Failed to fetch dataset GeoJSON.');
            }
            return response.json(); // Parse the response JSON
        })
        .then((data) => {
            featureCollection = data.collection; // Set the global variable
			featureCollection.features.forEach((feature, index) => feature.id = index);
            console.log(featureCollection);
            mappy.getSource('places').setData(featureCollection);
			mappy.fitBounds( bbox( featureCollection ), {
				padding: 30
			})
        })
        .catch((error) => {
            console.error(error);
        });
        
}

function buildSelect() {
	var select = '<label>Review filters: <select name="status" aria-controls="placetable" id="status_select" class="datatables_length">' +
		'<option value="99" selected="selected">All</option>'

	if (wdtask) {
		select +=
			'<option disabled>-----wikidata-----</option>' +
			'<option value="50">Needs review (wd)</option>' +
			'<option value="51">Reviewed (wd)</option>' +
			'<option value="52">Deferred (wd)</option>'
	}
	if (tgntask) {
		select +=
			'<option disabled>-------tgn-------</option>' +
			'<option value="60">Needs review (tgn)</option>' +
			'<option value="61">Reviewed (tgn)</option>' +
			'<option value="62">Deferred (tgn)</option>'
	}
	if (whgtask) {
		select +=
			'<option disabled>-------whg-------</option>' +
			'<option value="70">Needs review (whg)</option>' +
			'<option value="71">Reviewed (whg)</option>' +
			'<option value="72">Deferred (whg)</option>'
	}

	select += '</select></label>'
	return select
}

function filterColumn(i, v) {
	// clear then search
	console.log('filterColumn', i, v, typeof(i))
	table
		.columns([7, 8])
		.search('')
		.columns(i)
		.search(v)
		.draw();
	$("#status_select").val(localStorage.getItem('filter'))
}

function clearFilters() {
	// clear
	table
		.columns([5, 6, 7])
		.search('')
		.draw();
	$("#status_select").val('99')
}