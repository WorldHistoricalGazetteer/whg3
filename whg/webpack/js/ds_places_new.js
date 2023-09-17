// /whg/webpack/js/ds_places_new.js

import { envelope } from './6.5.0_turf.min.js' 
import { mappy, mapPadding, mapBounds, features, datasetLayers, filteredLayer, dateline } from './maplibre_whg';
import ClipboardJS from '/webpack/node_modules/clipboard'; 

let checked_rows;
let highlightedFeatureIndex;
let table;

$("[rel='tooltip']").tooltip();

var clip_cite = new ClipboardJS('#a_clipcite');
clip_cite.on('success', function(e) {
	console.log('clipped')
	e.clearSelection();
	$("#a_clipcite").tooltip('hide')
		.attr('data-original-title', 'copied!')
		.tooltip('show');
});

$("#clearlines").click(function() {
	mappy.removeLayer('gl_active_poly')
	mappy.removeLayer('outline')
})

$("#create_coll_link").click(function() {
	console.log('open title input')
	$("#title_form").show()
})

// Apply/Remove filters when dateline control is toggled
$("body").on("click", ".dateline-button", function() {
	toggleFilters( $('.range_container.expanded').length > 0 );
});

// Custom search function to filter table based on dateline.fromValue and dateline.toValue
$.fn.dataTable.ext.search.push(function (settings, data, dataIndex) {
	if ( $('.range_container.expanded').length == 0) { // Is dateline inactive?
		return true;
	}
	
    const fromValue = dateline.fromValue;
    const toValue = dateline.toValue;
    const includeUndated = dateline.includeUndated
    
    // Get the min and max values from the data attributes of the row
    const row = $(settings.aoData[dataIndex].nTr);
    const minData = row.attr('data-min');
    const maxData = row.attr('data-max');

    // Convert minData and maxData to numbers for comparison
    const min = minData === 'null' ? 'null' : parseFloat(minData);
	const max = maxData === 'null' ? 'null' : parseFloat(maxData);

    // Filter logic
	if (((!isNaN(fromValue) && !isNaN(toValue)) && (min !== 'null' && max !== 'null' && min <= toValue && max >= fromValue)) || (includeUndated && (min === 'null' || max === 'null'))) {
        return true; // Include row in the result
    }
    return false; // Exclude row from the result
});

function toggleFilters(on){
    datasetLayers.forEach(function(layer){
		mappy.setFilter(layer.id, on ? filteredLayer(layer).filter : layer.filter);
	});
	table.draw();
}

export function dateRangeChanged(fromValue, toValue){
	// Throttle date slider changes using debouncing
	// Ought to be possible to use promises on the `render` event
	let debounceTimeout;
    function debounceFilterApplication() {
        clearTimeout(debounceTimeout);
        debounceTimeout = setTimeout(toggleFilters(true), 300);
    }
    debounceFilterApplication(); 
}

function resetSearch() {
	var e = $.Event('keyup')
	e.which(13)
	$("#placetable_filter input").trigger(e)
}

// pids generate new CollPlace (collection_collplace) and
// TraceAnnotation records (trace_annotations
// same function in place_portal.html
function add_to_collection(coll, pids) {
	console.log('add_to_collection()')
	var formData = new FormData()
	formData.append('collection', coll)
	formData.append('place_list', pids)
	formData.append('csrfmiddlewaretoken', '{{ csrf_token }}');
	/* collection.views.add_places() */
	$.ajax({
		type: 'POST',
		enctype: 'multipart/form-data',
		url: '/collections/add_places/',
		processData: false,
		contentType: false,
		cache: false,
		data: formData,
		success: function(response) {
			var dupes = response.msg.dupes
			var added = response.msg.added
			if (dupes.length > 0) {
				let msg = dupes.length + ' records ' + (dupes.length > 1 ? 'were' : "was") + ' already in the collection: [' + dupes
				if (added.length > 0) {
					msg += ']; ' + added.length + ' ' + (added.length > 1 ? 'were' : "was") + ' added'
				}
				alert(msg)
			} else {
				// notify success & clear checks and list
				$("#added_flash").fadeIn().delay(2000).fadeOut()
				checked_rows = []
			}
			// uncheck everything regardless
			$(".table-chk").prop('checked', false)
		}
	})
	// TODO: notify of success
	console.log('add_to_collection() completed')
	/*$("#addtocoll").hide()*/
	$("#addtocoll_popup").hide()
	$("#sel_count").html('')
	$("#selection_status").css('display', 'none')
	/*$("input.action").prop('checked',false)*/
	/*resetSearch()*/
}
$(".a_addtocoll").click(function() {
	coll = $(this).attr('ref')
	pids = checked_rows
	add_to_collection(coll, pids)
	/*console.log('pids to coll', pids, coll)*/
})
$("#b_create_coll").click(function() {
	let title = $("#title_input").val()
	if (title != '') {
		// create new place collection, return id
		var formData = new FormData()
		formData.append('title', title)
		formData.append('csrfmiddlewaretoken', '{{ csrf_token }}');
		$.ajax({
			type: 'POST',
			enctype: 'multipart/form-data',
			url: '/collections/flash_create/',
			processData: false,
			contentType: false,
			cache: false,
			data: formData,
			success: function(data) {
				el = $('<li><a class="a_addtocoll" href="#" ref=' + data.id + '>' + data.title + '</a></li>')
				el.click(function() {
					coll = data.id
					pids = checked_rows
					add_to_collection(coll, pids)
					console.log('pids to coll', pids, coll)
				})
				$("#my_collections").append(el)
			}
		})
		$("#title_form").hide()
	} else {
		alert('Your new collection needs a title!')
	}
})

function filterColumn(i, v) {
	// clear then search
	table
		.columns([1])
		.search('')
		.columns(i)
		.search(v)
		.draw();
	$("#status_select").val(localStorage.getItem('filter'))
}

function clearFilters() {
	// clear
	table
		.columns([1])
		.search('')
		.draw();
	$("#status_select").val('99')
}

function highlightFeature(pid) {
	
	var featureIndex = features.findIndex(f => f.properties.pid === parseInt(pid)); // .addSource 'generateId': true doesn't create a findable .id property
	if (featureIndex !== -1) {
		if (highlightedFeatureIndex !== undefined) mappy.setFeatureState({ source: 'places', id: highlightedFeatureIndex }, { highlight: false });
	    var feature = features[featureIndex];
		const geom = feature.geometry;
		if (geom) {
			const coords = geom.coordinates;
			highlightedFeatureIndex = featureIndex;
			mappy.setFeatureState({ source: 'places', id: featureIndex }, { highlight: true });
			
			// zoom to feature
			if (geom.type.toLowerCase() == 'point') {
				const flycoords = typeof(coords[0]) == 'number' ? coords : coords[0]
				const mapBounds = {
					'center': flycoords,
					'zoom': 7
				}
				mappy.flyTo({
					...mapBounds,
					padding: mapPadding
				})
			} else {
				mapBounds = envelope(geom).bbox
				mappy.fitBounds(mapBounds, {
					padding: mapPadding
				})
			}
		}
		else {
			console.log('Feature in clicked row has no geometry.');
		}
	} else {
	    console.log(`Feature ${pid} not found.`);
	}
	
}

// TODO: use datatables methods?
// Listen for table row click (assigned using event delegation to allow for redrawing)
$("body").on("click", "#placetable tbody tr", function() {
	const thisy = $(this)
	// get id
	const pid = $(this)[0].cells[0].textContent
	// is checkbox checked?
	// if not, ensure row pid is not in checked_rows
	if (loggedin == true) {
		chkbox = thisy[0].cells[3].firstChild
		if (chkbox.checked) {
			console.log('chkbox.checked')
			checked_rows.push(pid)
			$("#selection_status").fadeIn()
			/*$("#addtocoll").fadeIn()*/
			console.log('checked_rows', checked_rows)
			$("#sel_count").html(' ' + checked_rows.length + ' ')
		} else {
			const index = checked_rows.indexOf(pid);
			if (index > -1) {
				checked_rows.splice(index, 1)
				if (checked_rows.length == 0) {
					$("#addtocoll").fadeOut()
					$("#addtocoll_popup").hide()
				}
			}
			console.log(pid + ' removed from checked_rows[]', checked_rows)
		}
	}
	
	// highlight this row, clear others
	var selected = $(this).hasClass("highlight-row");
	$("#placetable tr").removeClass("highlight-row");

	if (!selected)
		$(this).removeClass("rowhover");
	$(this).addClass("highlight-row");
	
	// fetch its detail
	getPlace(pid);
	
	highlightFeature(pid);

});

function highlightFirstRow() {
	$("#placetable tr").removeClass("highlight-row");
	const row = $("#ds_table table tbody")[0].rows[0]
	const pid = parseInt(row.cells[0].textContent)
	// highlight first row, fetch detail, but don't zoomTo() it
	$("#placetable tbody").find('tr').eq(0).addClass('highlight-row')
	getPlace(pid)
}

// Adjust the DataTable's page length to avoid scrolling where possible
function adjustPageLength() {
    const dsTable = document.getElementById('ds_table');
    const tableFilter = document.getElementById('placetable_filter');
    const tablePaginate = document.getElementById('placetable_paginate');
    const theadRow = document.querySelector('#placetable thead tr');
    const tbody = document.querySelector('#placetable tbody');
    const availableHeight = dsTable.clientHeight - (2 * 10 /*padding*/) - tableFilter.clientHeight - tablePaginate.clientHeight - theadRow.clientHeight;
    const averageRowHeight = 2 + ( tbody.clientHeight / document.querySelectorAll('#placetable tr:not(thead tr)').length );
    let estimatedRowsPerPage = Math.floor(availableHeight / ( averageRowHeight ));
  	// Ensure a minimum of 5 rows
  	estimatedRowsPerPage = Math.max(estimatedRowsPerPage, 5);
	console.log(`Changing table length to ${estimatedRowsPerPage} rows @${averageRowHeight} pixels.`);
  	const DataTable = $('#placetable').DataTable();
  	DataTable.page.len(estimatedRowsPerPage).draw();
}

$(".table-chk").click(function(e) {
	e.preventDefault()
	console.log('adding', $(this).data('id'))
	/*console.log('checked_rows',checked_rows)*/
})

export function initialiseTable() {
	
	console.log('initialiseTable', features);
	
	// START ds_info controls
	var isCollapsed = localStorage.getItem('isCollapsed') === 'true';

	// Set initial height and icon
	if (isCollapsed) {
		$('#ds_info').css('height', '40px');
		$('#expandIcon').show();
		$('#collapseIcon').hide();
		$('#iconLabel').text('Show Detail');
	}

	$('#toggleIcon').click(function() {
		if (isCollapsed) {
			// if the div is collapsed, expand it to fit its content
			$('#ds_info').css('height', 'fit-content');
			$('#expandIcon').hide();
			$('#collapseIcon').show();
			$('#iconLabel').text('Hide');
			isCollapsed = false;
		} else {
			// if the div is not collapsed, animate it to 40px height
			$('#ds_info').css('height', '40px');
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

	checked_rows = []
	localStorage.setItem('filter', '99')
	var wdtask = false
	var tgntask = false
	var whgtask = false

	/*loggedin = {{ loggedin }}*/
	const check_column = loggedin == true ? {
		data: "properties.pid",
      	render: function (data, type, row) {
        	return `<input type="checkbox" name="addme" class="table-chk" data-id="${data}"/>`;
      	},
	} : {
		"data": "properties.pid",
		"visible": false
	}

	startTableSpinner()
	startDetailSpinner()

	// task columns are inoperable in this public view
	table = $('#placetable').DataTable({
		/*dom:  "<'row small'<'col-sm-12 col-md-4'l>"+*/
		dom: "<'row small'<'col-sm-7'f>" +
			"<'col-sm-5'>>" +
			"<'row'<'col-sm-12'tr>>" +
			"<'row small'<'col-sm-12'p>>",
		// scrollY: 400,
		select: true,
		order: [
			[0, 'asc']
		],
		//pageLength: 250,
		//LengthMenu: [25, 50, 100],
		data: features,
		columns: [
			{
		      data: "properties.pid",
		      render: function (data, type, row) {
		        return `<a href="http://localhost:8000//api/db/?id=${data}" target="_blank">${data}</a>`;
		      }
		    },
		    {
		      data: "properties.title"
		    },
		    {
				data: "geometry",
	            render: function (data, type, row) {
	                if (data) {
	                    return `<img src="/static/images/geo_${data.type.toLowerCase().replace('multi','')}.svg" width=12/>`;
	                } else {
	                    return "<i>none</i>";
	                }
	            }
		    },
		    check_column
		],
		columnDefs: [
			/*{ className: "browse-task-col", "targets": [8,9,10] },*/
			/*{ orderable: false, "targets": [4, 5]},*/
			{
				orderable: false,
				"targets": [0, 2, 3]
			},
			{
				searchable: false,
				"targets": [0, 2, 3]
			}
			/*, {visible: false, "targets": [5]}*/
			/*, {visible: false, "targets": [0]}*/
		],
		rowId: 'properties.pid',
	    createdRow: function (row, data, dataIndex) {
	        // Attach temporal min and max properties as data attributes
	        $(row).attr('data-min', data.properties.min);
	        $(row).attr('data-max', data.properties.max);
			if (!data.geometry) {
		        $(row).addClass('no-geometry');
		    }
			if (data.properties.min === 'null' || data.properties.max === 'null') {
		        $(row).addClass('no-temporal');
		    }
	    },
	    initComplete: function(settings, json) {
	        adjustPageLength();
	    },
	    drawCallback: function(settings) {
			console.log('table drawn')
			spinner_table.stop()
			// recheck inputs in checked_rows
			if (checked_rows.length > 0) {
				for (i in checked_rows) {
					$('[data-id=' + checked_rows[i] + ']').prop('checked', true)
				}
				// make sure selection_status is visible
				$("#selection_status").show()
			}
			highlightFirstRow();
	    }
	})

	$("#addchecked").click(function() {
		console.log('clicked #addchecked')
		$("#addtocoll_popup").fadeIn()
	})

	$(".closer").click(function() {
		$("#addtocoll_popup").hide()
	})

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
}

// activate all tooltips
$("[rel='tooltip']").tooltip();

export function getPlace(pid) {
	console.log('getPlace()', pid);
    if (isNaN(pid)) {
        console.log('Invalid pid');
        return;
    }
	$.ajax({
		url: "/api/place/" + pid,
	}).done(function(data) {
		$("#detail").html(parsePlace(data))
		spinner_detail.stop()
		// events on detail items
		$('.ext').on('click', function(e) {
			e.preventDefault();
			str = $(this).text()
			//console.log('str (identifier)',str)-->
			// URL identifiers can be 'http*' or an authority prefix
			if (str.substring(0, 4).toLowerCase() == 'http') {
				url = str
			} else {
				var re = /(http|bnf|cerl|dbp|gn|gnd|gov|loc|pl|tgn|viaf|wd|wdlocal|whg|wp):(.*?)$/;
				url = base_urls[str.match(re)[1]] + str.match(re)[2]
				console.log('url', url)
			}
			window.open(url, '_blank');
		});
		$('.exttab').on('click', function(e) {
			e.preventDefault();
			id = $(this).data('id')
			console.log('id', id)
			var re = /(http|dbp|gn|tgn|wd|loc|viaf|aat):(.*?)$/;
			url = id.match(re)[1] == 'http' ? id : base_urls[id.match(re)[1]] + id.match(re)[2]
			console.log('url', url)
			window.open(url, '_blank')
		});
	});
	//spinner_detail.stop()-->
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
	//timespan_arr = []-->
	//
	// TITLE 
	var descrip = '<p><b>Title</b>: <span id="row_title" class="larger text-danger">' + data.title + '</span>'
	//
	// NAME VARIANTS
	descrip += '<p class="scroll65"><b>Variants</b>: '
	for (var n in data.names) {
		let name = data.names[n]
		descrip += '<p>' + name.toponym != '' ? name.toponym + '; ' : ''
	}
	//
	// TYPES
	// may include sourceLabel:"" **OR** sourceLabels[{"label":"","lang":""},...]
	// console.log('data.types',data.types)
	//{"label":"","identifier":"aat:___","sourceLabels":[{"label":" ","lang":"en"}]}
	descrip += '</p><p><b>Types</b>: '
	var typeids = ''
	for (var t in data.types) {
		var str = ''
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
	//close_count = added_count = related_count = 0
	var html = ''
	if (data.links.length > 0) {
		links = data.links
		links_arr = onlyUnique(data.links)
		/*console.log('distinct data.links',links_arr)*/
		for (l in links_arr) {
			descrip += url_extplace(links_arr[l].identifier)
		}
	} else {
		descrip += "<i class='small'>no links established yet</i>"
	}
	descrip += '</p>'

	//
	// RELATED
	//right=''-->
	if (data.related.length > 0) {
		parent = '<p class="mb-0"><b>Parent(s)</b>: ';
		related = '<p class="mb-0"><b>Related</b>: ';
		for (r in data.related) {
			rel = data.related[r]
			//console.log('rel',rel)-->
			if (rel.relation_type == 'gvp:broaderPartitive') {
				parent += '<span class="small h1em">' + rel.label
				parent += 'when' in rel && !('timespans' in rel.when) ?
					', ' + rel.when.start.in + '-' + rel.when.end.in :
					'when' in rel && ('timespans' in rel.when) ? ', ' +
					minmaxer(rel.when.timespans) : ''
				//rel.when.timespans : ''-->
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
		//'<br/><span class="small red-bold">('+data.descriptions[0]['identifier']+')</span>-->
	}
	//
	// CCODES
	//
	//if (data.ccodes.length > 0) {-->
	if (!!data.countries) {
		//console.log('data.countries',data.countries)-->
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
		link = '<a href="' + identifier + '" target="_blank">' + tag + '<i class="fas fa-external-link-alt linky"></i>,  </a>';
	} else {
		link = '<a href="" class="ext" data-target="#ext_site">' + identifier + '&nbsp;<i class="fas fa-external-link-alt linky"></i></a>, ';
	}
	return link
}

// builds link for external placetype record
function url_exttype(type) {
	const link = ' <a href="#" class="exttab" data-id=' + type.identifier +
		'>(' + type.label + ' <i class="fas fa-external-link-alt linky"></i>)</a>'
	return link
}

function minmaxer(timespans) {
	//console.log('got to minmax()',JSON.stringify(timespans))-->
	starts = [];
	ends = []
	for (t in timespans) {
		// gets 'in', 'earliest' or 'latest'
		starts.push(Object.values(timespans[t].start)[0])
		ends.push(!!timespans[t].end ? Object.values(timespans[t].end)[0] : -1)
	}
	//console.log('starts',starts,'ends',ends)-->
	minmax = [Math.max.apply(null, starts), Math.max.apply(null, ends)]
	return minmax
}

// spinners
const spin_opts = {
	scale: .5,
	top: '50%'
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
	console.log('startMapSpinner()')
	window.spinner_map = new Spin.Spinner(spin_opts).spin();
	$("#map_browse").append(spinner_map.el);
}
//*
