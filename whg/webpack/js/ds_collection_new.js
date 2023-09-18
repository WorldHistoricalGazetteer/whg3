$(".a-dl").click(function(e) {
	e.preventDefault()
	alert('not yet')
})

function filterColumn(i, v) {
	// clear then search
	table
		.search('')
		.columns(i)
		.search(v)
		.draw();
	$("#ds_select").val(localStorage.getItem('filter'))
}

function clearFilters() {
	// clear
	table
		.columns([5, 6, 7, 11])
		.search('')
		.draw();
	$("#ds_select").val('-1')
}

// table events
// TODO: use datatables methods?
function setRowEvents() {
	$("#ds_select").change(function(e) {
		// filter table
		val = $(this).val()
		localStorage.setItem('filter', val)
		startMapSpinner()
		if (val == -1) {
			// clear search
			startFilterSpinner()
			clearFilters()
		} else {
			clearFilters()
			filterColumn(11, val)
		}
		// also filter map
		filterMap(val)
	})

	$("#placetable tbody tr").click(function() {
		thisy = $(this)
		// get id
		pid = $(this)[0].cells[0].textContent
		ds_src = table.row(thisy.index()).data().dataset.label

		geom = all_feats.find(function(f) {
			return f.properties.pid == pid
		}).geometry
		coords = geom.coordinates

		// fetch its detail
		getPlace(pid, 'clicked')

		// highlight this row, clear others
		var selected = $(this).hasClass("highlight-row");
		$("#placetable tr").removeClass("highlight-row");

		if (!selected)
			$(this).removeClass("rowhover");
		$(this).addClass("highlight-row");

		// highlight marker, zoomTo()
		highlightFeatureGL(pid, geom, coords, ds_src)

	})

	row = $("#ds_table tbody")[0].rows[0]
	pid = parseInt(row.cells[0].textContent)
	// highlight first row, fetch detail, but don't zoomTo() it
	$("#placetable tbody").find('tr').eq(0).addClass('highlight-row')
	// fetch place details for 1st row
	getPlace(pid, 'row0')
}

function buildSelect() {
	select = '<label>Datasets: <select id="ds_select">' +
		'<option value="-1" selected="selected">All</option>'
	for (let ds of ds_list) {
		select += '<option value="' + ds.label + '" selected="selected">' +
			ds.title + '</option>'
	}
	select += '</select></label>'
	return select
}

$(function() {
	// START dscoll_info controls
	var isCollapsed = localStorage.getItem('isCollapsed') === 'true';

	// Set initial height and icon
	if (isCollapsed) {
		$('#dscoll_info').css('height', '40px');
		$('#expandIcon').show();
		$('#collapseIcon').hide();
		$('#iconLabel').text('Show Detail');
	}

	$('#toggleIcon').click(function() {
		if (isCollapsed) {
			// if the div is collapsed, expand it to fit its content
			$('#dscoll_info').css('height', 'fit-content');
			$('#expandIcon').hide();
			$('#collapseIcon').show();
			$('#iconLabel').text('Hide');
			isCollapsed = false;
		} else {
			// if the div is not collapsed, animate it to 40px height
			$('#dscoll_info').css('height', '40px');
			$('#expandIcon').show();
			$('#collapseIcon').hide();
			$('#iconLabel').text('Show Detail');
			isCollapsed = true;
		}

		// Store the state in local storage
		localStorage.setItem('isCollapsed', isCollapsed);
	});

	// Update the state when the checkbox is checked
	$('#checkbox').change(function() {
		localStorage.setItem('isCollapsed', $(this).is(':checked'));
	});
	// END ds_info controls


	window.ds_list = JSON.parse(document.getElementById('ds_list').textContent);
	source_list = ds_list.map(function(d) {
		return d.label
	})
	window.layer_list = getLoadedLayers()

	$("#ds_filter").html(buildSelect());
	// TODO: remove these artifacts of table used for review
	localStorage.setItem('filter', '-1')
	wdtask = "{{wdtask}}" == "True" ? true : false
	tgntask = "{{tgntask}}" == "True" ? true : false
	whgtask = "{{whgtask}}" == "True" ? true : false

	// start spinners, some collections take time
	startMapSpinner()
	startTableSpinner()
	startDetailSpinner()

	window.filter = "{{ filter }}"
	// initialize table
	// task columns are inoperable in this public view
	table = $('#placetable').DataTable({
		dom: "<'row small'<'col-sm-10'p><'col-sm-2'>>" +
			"<'row'<'col-sm-12'tr>>" +
			"<'row small'<'col-sm-12'f>>",
		serverSide: true,
		ajax: {
			url: "/api/placetable_coll/?format=datatables&id={{ object.id }}"
		},
		scrollY: 400,
		select: true,
		order: [
			[2, 'asc']
		],
		pageLength: 25,
		LengthMenu: [25, 50, 100],
		columns: [{
				"data": "id"
			},
			{
				"data": "title"
			},
			{
				"title": "geom",
				"data": "geo"
			},
			{
				"data": "dataset.label",
				"name": "dataset.label"
			}
		],
		columnDefs: [{
				orderable: false,
				"targets": [0, 2, 3]
			},
			{
				searchable: false,
				"targets": [0, 2, 3]
			}, {
				visible: false,
				"targets": [3]
			}
		]
	})


	table.on('draw', function() {
		$("#ds_select").val(localStorage.getItem('filter'))
		spinner_table.stop()
		setRowEvents();
	})

	// help popups
	$(".help-matches").click(function() {
		page = $(this).data('id')
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
}) //** end onload()

// gl map
mappy = new maptilersdk.Map({
	container: 'map', // container id
	style: 'mapbox://styles/mapbox/light-v10',
	center: [9.2, 33],
	zoom: 0.2, // starting zoom
	minZoom: 0.1,
	maxZoom: 12,
	accessToken: '{{ mbtoken }}'
});

// mappy.on('idle', function(e) {
//   console.log('idle e', e.target.painter.currentStencilSource)
// })
// TODO: add a 'big?' boolean to ds_list based on count of polygons
mappy.on('sourcedata', function(e) {
	// console.log('source_list', source_list)
	if (source_list.includes('territorios892')) {
		// big polygons
		if (e.sourceId == 'territorios892' && e.isSourceLoaded) {
			spinner_map.stop()
			$(".toomany").html('').hide()
		}
	} else {
		spinner_map.stop()
		$(".toomany").html('').hide()
	}
});

mappy.on('load', function() {
	hilited = null

	// initialize empty layers for z-index ordering
	mappy.addSource('empty', {
		type: 'geojson',
		data: {
			type: 'FeatureCollection',
			features: []
		}
	});

	const zIndex4 = mappy.addLayer({
		id: 'z-index-4',
		type: 'symbol',
		source: 'empty'
	}); //top

	const zIndex3 = mappy.addLayer({
		id: 'z-index-3',
		type: 'symbol',
		source: 'empty'
	}, 'z-index-4'); // below zIndex4

	const zIndex2 = mappy.addLayer({
		id: 'z-index-2',
		type: 'symbol',
		source: 'empty'
	}, 'z-index-3'); // below zIndex3

	const zIndex1 = mappy.addLayer({
		id: 'z-index-1',
		type: 'symbol',
		source: 'empty'
	}, 'z-index-2'); // place this layer below zIndex2

	// generate sources, layers from sources, render them
	addSources(ds_list)

	// set mouseenter and click events (popup) for map markers
	layer_list = getLoadedLayers(ds_list)
	for (l in layer_list) {
		// TODO: allow clicking on polygons and linestrings, denied here
		//if(layer_list[l].indexOf('point') != -1){
		mappy.on('mouseenter', layer_list[l], function() {
			mappy.getCanvas().style.cursor = 'pointer';
		});

		// Change it back to a pointer when it leaves.
		mappy.on('mouseleave', layer_list[l], function() {
			mappy.getCanvas().style.cursor = '';
		});
		// differentiate circle, fill, line
		mappy.on('click', layer_list[l], function(e) {
			ftype = e.features[0].layer.type
			geom = e.features[0].geometry
			coords = e.features[0].geometry.coordinates
			place = e.features[0]
			if (ftype == 'point') {
				var coordinates = e.features[0].geometry.coordinates.slice();
			} else if (ftype == 'line') {
				segment = turf.lineString(coords[Math.round(coords.length / 2)])
				len = turf.length(segment)
				var coordinates = turf.along(segment, len / 2).geometry.coordinates
			} else {
				var coordinates = turf.centroid(e.features[0].geometry).geometry.coordinates
			}
			var pid = e.features[0].properties.pid;
			var title = e.features[0].properties.title;
			var src_id = e.features[0].properties.src_id;
			var min = e.features[0].properties.min;
			var max = e.features[0].properties.max;
			var fc = e.features[0].properties.fclasses;

			while (Math.abs(e.lngLat.lng - coordinates[0]) > 180) {
				coordinates[0] += e.lngLat.lng > coordinates[0] ? 360 : -360;
			}

			// highlight row
			//console.log('highlight row & fetch data', pid, coordinates)-->

			// popup
			html = '<b>' + title + '</b><br/>' +
				'<a href="javascript:getPlace(' + pid + ')">fetch info</a><br/>'
			if (min) {
				html += 'start: ' + min + ', end:' + max ?? ''
			}
			new maplibregl.Popup()
				.setLngLat(coordinates)
				.setHTML(html)
				.addTo(mappy);
		})
		//}
	}
});

function getLoadedLayers(ds_list) {
	layers = []
	for (d in ds_list) {
		l = ds_list[d]['label']
		layers.push('gl_' + l + '_point')
		layers.push('gl_' + l + '_poly')
		layers.push('gl_' + l + '_line')
	}
	return layers
}

// for each dataset, fetch places, create map source, append features to all_feats[] (why?),
// pass to renderSourceLayers() to add up to 3 layers to map per source type (point, poly, line)
function addSources(ds_list) {
	all_feats = []
	source_list = []
	$(".toomany").html('please wait...rendering many polygons').show()
	startMapSpinner()
	ds_list.forEach(function(ds, i) {
		$.getJSON('/datasets/' + ds.id + '/geojson')
			.done(function(dsdata) {
				mappy.addSource(ds.label, {
					'type': 'geojson',
					'data': dsdata.collection
				});
				all_feats = all_feats.concat(dsdata.collection.features)
				renderSourceLayers(ds.label, i)
			})
		source_list.push(ds.label)
	})
}

// TODO: better colors
colors_point = ['#ff9900', 'red', 'green', 'blue', 'purple',
	'#ff9900', 'red', 'green', 'blue', 'purple'
]
colors_poly = ['#eee', 'aliceblue']

// render dataset/geometry layers
function renderSourceLayers(dslabel, i) {
	startMapSpinner()
	mappy.addLayer({
		'id': 'gl_' + dslabel + '_poly',
		'type': 'fill',
		'source': dslabel,
		'visibility': 'visible',
		'paint': {
			'fill-color': '#FFDBD3',
			'fill-opacity': 0.5,
			'fill-outline-color': '#000'
		},
		'filter': ['==', '$type', 'Polygon']
	}, 'z-index-1');

	mappy.addLayer({
		'id': 'gl_' + dslabel + '_point',
		'type': 'circle',
		'source': dslabel,
		'visibility': 'visible',
		'paint': {
			'circle-color': colors_point[i],
			'circle-radius': {
				stops: [
					[1, 2],
					[3, 3],
					[16, 10]
				]
			}
		},
		'filter': ['==', '$type', 'Point']
	}, 'z-index-2');

	mappy.addLayer({
		'id': 'gl_' + dslabel + '_line',
		'type': 'line',
		'source': dslabel,
		'paint': {
			'line-color': 'blue',
			'line-width': {
				stops: [
					[1, 2],
					[4, 2],
					[16, 4]
				]
			}
		},
		'filter': ['==', '$type', 'LineString']
	}, 'z-index-3');

	fcoll = {
		"type": "FeatureCollection",
		"features": all_feats
	}
	mappy.fitBounds(turf.bbox(fcoll), {
		padding: 20
	});
}

function layerColors() {
	obj = {}
	for (l in layer_list) {
		obj[layer_list[l]] = mappy.getLayer(layer_list[l]).getPaintProperty('circle-color')
	}
}
// hightlight selected in row
function highlightFeatureGL(pid, geom, coords, src) {

	//mappy.getLayer(layer_list[4]).getPaintProperty('circle-color')
	mappy.setPaintProperty(
		'gl_' + src + '_point', 'circle-radius', {
			'property': 'pid',
			'type': 'categorical',
			'default': 3,
			'stops': [
				[Number(pid), 8]
			]
		}
	);
	mappy.setPaintProperty(
		'gl_' + src + '_point', 'circle-stroke-color', {
			'property': 'pid',
			'type': 'categorical',
			'stops': [
				[Number(pid), '#666']
			]
		}
	);
	mappy.setPaintProperty(
		'gl_' + src + '_point', 'circle-stroke-width', {
			'property': 'pid',
			'type': 'categorical',
			'stops': [
				[Number(pid), 1]
			]
		}
	);
	mappy.setPaintProperty(
		'gl_' + src + '_point', 'circle-color', {
			'property': 'pid',
			'default': 'red',
			'type': 'categorical',
			'stops': [
				[Number(pid), 'yellow']
			]
		}
	);
	mappy.setPaintProperty(
		'gl_' + src + '_point', 'circle-opacity', {
			'property': 'pid',
			'default': 0.5,
			'type': 'categorical',
			'stops': [
				[Number(pid), 1]
			]
		}
	);
	mappy.setPaintProperty(
		'gl_' + src + '_poly', 'fill-outline-color', {
			'property': 'pid',
			'type': 'categorical',
			'stops': [
				[Number(pid), 'red']
			]
		}
	);
	mappy.setPaintProperty(
		'gl_' + src + '_poly', 'fill-color', {
			'property': 'pid',
			'default': "rgba(255,255,255,0.0)",
			'type': 'categorical',
			// 'stops':[[Number(pid), 'red']]}
			'stops': [
				[Number(pid), 'rgba(0,128,0,1.0)']
			]
		}
	);
	// also set z-index and zoom

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

// activate all tooltips
$("[rel='tooltip']").tooltip();

// show/hide dataset markers from dropdown
// TODO: this seems inefficient but works
function filterMap(key) {
	console.log('filter on ds', key)
	if (key == -1) {
		for (l in layer_list) {
			mappy.setLayoutProperty(layer_list[l], 'visibility', 'visible')
			mappy.fitBounds(turf.bbox(fcoll), {
				padding: 20
			});
		}
	} else {
		relevant = layer_list.filter(l => l.indexOf(key) != -1)
		others = layer_list.filter(l => !relevant.includes(l))
		for (l in others) {
			mappy.setLayoutProperty(others[l], 'visibility', 'none')
		}
		for (l in relevant) {
			mappy.setLayoutProperty(relevant[l], 'visibility', 'visible')
		}
		bounds = ds_list.find((o) => {
			return o['label'] === key
		}).bounds
		mappy.fitBounds(turf.envelope(bounds).bbox)
	}
}

function getPlace(pid, from) {
	$.ajax({
		url: "/api/place/" + pid,
	}).done(function(data) {
		// if geom is polygon, make feature & add to map if not initial table.draw()
		$("#detail").html(parsePlace(data))
		spinner_detail.stop()
		// events on detail items
		$('.ext').on('click', function(e) {
			e.preventDefault();
			str = $(this).text()
			// console.log('str (identifier)',str)
			// URL identifiers can be 'http*' or an authority prefix
			if (str.substring(0, 4).toLowerCase() == 'http') {
				url = str
			} else {
				var re = /(http|bnf|cerl|dbp|gn|gnd|gov|loc|pl|tgn|viaf|wd|wdlocal|whg|wp):(.*?)$/;
				url = base_urls[str.match(re)[1]] + str.match(re)[2]
			}
			window.open(url, '_blank');
		});
		$('.exttab').on('click', function(e) {
			e.preventDefault();
			id = $(this).data('id')
			var re = /(http|dbp|gn|tgn|wd|loc|viaf|aat):(.*?)$/;
			url = id.match(re)[1] == 'http' ? id : base_urls[id.match(re)[1]] + id.match(re)[2]
			window.open(url, '_blank')
		});
	});
}

// single column
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
	//
	// TITLE
	descrip = '<p><b>Title</b>: <span id="row_title" class="larger text-danger">' + data.title + '</span>'
	//
	// NAME VARIANTS
	descrip += '<p class="scroll65"><b>Variants</b>: '
	for (n in data.names) {
		let name = data.names[n]
		descrip += '<p>' + name.toponym != '' ? name.toponym + '; ' : ''
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
	descrip += '<p class="mb-0"><b>Links</b>: '
	close_count = added_count = related_count = 0
	html = ''
	if (data.links.length > 0) {
		links = data.links
		links_arr = onlyUnique(data.links)
		for (l in links_arr) {
			descrip += url_extplace(links_arr[l].identifier)
		}
	} else {
		descrip += "<i class='small'>no links established yet</i>"
	}
	descrip += '</p>'

	//
	// RELATED
	if (data.related.length > 0) {
		parent = '<p class="mb-0"><b>Parent(s)</b>: ';
		related = '<p class="mb-0"><b>Related</b>: ';
		for (r in data.related) {
			rel = data.related[r]
			if (rel.relation_type == 'gvp:broaderPartitive') {
				parent += '<span class="small h1em">' + rel.label
				parent += 'when' in rel && !('timespans' in rel.when) ?
					', ' + rel.when.start.in + '-' + rel.when.end.in :
					'when' in rel && ('timespans' in rel.when) ? ', ' +
					minmaxer(rel.when.timespans) : ''
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

	}
	//
	// CCODES
	//
	if (!!data.countries) {
		descrip += '<p><b>Modern country bounds</b>: ' + data.countries.join(', ') + '</p>'
	}
	//
	// MINMAX
	//
	if (data.minmax && data.minmax.length > 0) {
		descrip += '<p><b>When</b>: earliest: ' + data.minmax[0] + '; latest: ' + data.minmax[1]
	}
	descrip += '</div>'
	return descrip
}

// builds link for external place record
function url_extplace(identifier) {
	// abbreviate links not in aliases.base_urls
	if (identifier.startsWith('http')) {
		let tag = identifier.replace(/.+\/\/|www.|\..+/g, '')
		link = '<a href="' + identifier + '" target="_blank">' + tag + '<i class="fas fa-external-link-alt linky"></i>,  </a>'
	} else {
		link = '<a href="" class="ext" data-target="#ext_site">' + identifier + '&nbsp;<i class="fas fa-external-link-alt linky"></i></a>, '
	}
	return link
}

// builds link for external placetype record
function url_exttype(type) {
	link = ' <a href="#" class="exttab" data-id=' + type.identifier +
		'>(' + type.label + ' <i class="fas fa-external-link-alt linky"></i>)</a>'
	return link
}

styles = {
	"Point": {
		"default": {
			radius: 2,
			fillColor: "#ff9900",
			fillOpacity: 0.8,
			stroke: false
		},
		"focus": {
			radius: 8,
			fillColor: "#ffff00",
			fillOpacity: 1,
			stroke: true,
			weight: 1,
			color: "#000"
		}
	},
	"MultiPoint": {
		"default": {
			radius: 1,
			fillColor: "#ff9900",
			fillOpacity: 0.8,
			stroke: false
		},
		"focus": {
			radius: 8,
			fillColor: "#ffff00",
			fillOpacity: 1,
			stroke: true,
			weight: 1,
			color: "#000"
		}
	},
	"LineString": {
		"default": {
			opacity: 1,
			weight: 1,
			color: "#336699"
		},
		"focus": {
			opacity: 1,
			weight: 2,
			color: "blue"
		}
	},
	"MultiLineString": {
		"default": {
			opacity: 1,
			weight: 1,
			color: "#336699"
		},
		"focus": {
			opacity: 1,
			weight: 2,
			color: "blue"
		}
	},
	"MultiPolygon": {
		"default": {
			fillOpacity: 0.3,
			opacity: 1,
			color: "#000",
			weight: 1,
			fillColor: "#ff9999"
		},
		"focus": {
			fillOpacity: 0.3,
			opacity: 1,
			color: "red",
			weight: 2,
			fillColor: "#ff9999"
		}
	},
	"Polygon": {
		"default": {
			fillOpacity: 0.3,
			opacity: .5,
			color: "#666",
			weight: 1,
			fillColor: "#ff9999"
		},
		"focus": {
			fillOpacity: 0.3,
			opacity: .5,
			color: "red",
			weight: 2,
			fillColor: "#ff9999"
		}
	}
}

function minmaxer(timespans) {
	starts = [];
	ends = []
	for (t in timespans) {
		// gets 'in', 'earliest' or 'latest'
		starts.push(Object.values(timespans[t].start)[0])
		ends.push(!!timespans[t].end ? Object.values(timespans[t].end)[0] : -1)
	}
	minmax = [Math.max.apply(null, starts), Math.max.apply(null, ends)]
	return minmax
}

// spinners
const spin_opts = {
	scale: .5,
	top: '60%'
}

function startTableSpinner() {
	window.spinner_table = new Spin.Spinner(spin_opts).spin();
	$("#drftable_list").append(spinner_table.el);
}

function startFilterSpinner() {
	window.spinner_filter = new Spin.Spinner(spin_opts).spin();
	$("#status_filter").append(spinner_filter.el);
}

function startDetailSpinner() {
	window.spinner_detail = new Spin.Spinner(spin_opts).spin();
	$("#row_detail").append(spinner_detail.el);
}

function startMapSpinner() {
	window.spinner_map = new Spin.Spinner(spin_opts).spin();
	$(".toomany").append(spinner_map.el);
}