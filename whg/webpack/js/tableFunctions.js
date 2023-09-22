import { envelope } from './6.5.0_turf.min.js'
import { getPlace } from './getPlace';
import { startSpinner } from './utilities';
import { updatePadding, recenterMap, listSourcesAndLayers } from './mapFunctions';
import datasetLayers from './mapLayerStyles';

let table;

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

export function resetSearch() {
	var e = $.Event('keyup')
	e.which(13)
	$("#placetable_filter input").trigger(e)
}

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
    .columns([5, 6, 7, 11]) // TODO: Check these values?
    .search('')
    .draw();
    $("#ds_select").val('-1')
}

// TODO: ? Remove this version, which was apparently redundant in ds_places ?
/*export function filterColumn(i, v) {
	// clear then search
	table
		.columns([1])
		.search('')
		.columns(i)
		.search(v)
		.draw();
	$("#status_select").val(localStorage.getItem('filter'))
}*/

//  TODO: ? Remove this version, which was apparently redundant in ds_places ?
/*export function clearFilters() {
	// clear
	table
		.columns([1])
		.search('')
		.draw();
	$("#status_select").val('99')
}*/

function filterMap(mappy, val){
	let recentered = false;
	datasetLayers.forEach(function(layer) {
		window.ds_list.forEach(function(ds) {
			mappy.setLayoutProperty(`${layer.id}_${ds.id}`, 'visibility', (val == 'all' || ds.id.toString() === val.toString()) ? 'visible' : 'none');
			if (!recentered && ds.id.toString() === val.toString()) {
				recentered = true;
				window.mapBounds = ds.extent;
				recenterMap(mappy, 'lazy');
			}
		});
	});
}

export function highlightFeature(ds_pid, features, mappy) {
	
	//listSourcesAndLayers(mappy);
	
	features = features.filter(f => f.properties.dsid === ds_pid.ds);
	
	var featureIndex = features.findIndex(f => f.properties.pid === parseInt(ds_pid.pid)); 
	if (featureIndex !== -1) {
		//console.log(`Switching highlight from ${window.highlightedFeatureIndex} to ${featureIndex}.`);
		if (window.highlightedFeatureIndex !== undefined) mappy.setFeatureState(window.highlightedFeatureIndex, { highlight: false });
	    var feature = features[featureIndex];
		const geom = feature.geometry;
		if (geom) {
			const coords = geom.coordinates;
			window.highlightedFeatureIndex = {source: ds_pid.ds.toString(), id: featureIndex};
	    	console.log(feature,window.highlightedFeatureIndex);
			mappy.setFeatureState(window.highlightedFeatureIndex, { highlight: true });
			updatePadding();
			// zoom to feature
			if (geom.type.toLowerCase() == 'point') {
				const flycoords = typeof(coords[0]) == 'number' ? coords : coords[0]
				window.mapBounds = {
					'center': flycoords,
					'zoom': 7
				}
				recenterMap(mappy, 'lazy');
			} else {
				window.mapBounds = envelope(geom).bbox;
				recenterMap(mappy, 'lazy');
			}
			//console.log(`Highlight now on ${window.highlightedFeatureIndex}.`);
		}
		else {
			console.log('Feature in clicked row has no geometry.');
		}
	} else {
	    console.log(`Feature ${ds_pid.pid} not found.`);
	}
	
}

export function initialiseTable(features, checked_rows, spinner_table, spinner_detail, mappy) {

	checked_rows = []
	
	if (window.ds_list.length > 1) {
		let select = '<label>Datasets: <select id="ds_select">' +
        	'<option value="-1" data="all" selected="selected">All</option>';
        for (let ds of window.ds_list) {
            select += '<option value="' + ds.label + '" data="' + ds.id + '">' +
            ds.title + '</option>'
        }
        select += '</select></label>';
		$("#ds_filter").html(select);
	}
	
	// TODO: remove these artifacts of table used for review
	localStorage.setItem('filter', '99')
	var wdtask = false
	var tgntask = false
	var whgtask = false

	const check_column = window.loggedin ? {
		data: "properties.pid",
      	render: function (data, type, row) {
        	return `<input type="checkbox" name="addme" class="table-chk" data-id="${data}"/>`;
      	},
		visible: true
	} : {
		data: "properties.pid",
		visible: false
	}

	spinner_table = startSpinner("drftable_list");
	spinner_detail = startSpinner("row_detail");

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
			[1, 'asc']
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
		    {
		      data: "properties.dslabel"
		    },
		    check_column
		],
		columnDefs: [
			/*{ className: "browse-task-col", "targets": [8,9,10] },*/
			/*{ orderable: false, "targets": [4, 5]},*/
			{
				orderable: false,
				"targets": [0, 2, 4]
			},
			{
				searchable: false,
				"targets": [0, 2, 4]
			},
			{
				visible: window.ds_list.length > 1,
				"targets": [3]
			}
			/*, {visible: false, "targets": [5]}*/
			/*, {visible: false, "targets": [0]}*/
		],
		rowId: 'properties.pid',
	    createdRow: function (row, data, dataIndex) {
	        // Attach temporal min and max properties as data attributes
	        $(row).attr('data-min', data.properties.min);
	        $(row).attr('data-max', data.properties.max);
	        $(row).attr('dsid', data.properties.dsid);
	        $(row).attr('pid', data.properties.pid);
	        $(row).data('ds_pid', {ds: data.properties.dsid, pid: data.properties.pid});
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
	
    $("#ds_select").change(function (e) {
        // filter table
        let val = $(this).val()
        localStorage.setItem('filter', val)
        window.spinner_map = startSpinner("dataset_content", 3);
        if (val == -1) {
            // clear search
            window.spinner_filter = startSpinner("status_filter");
            clearFilters()
        } else {
            clearFilters()
            filterColumn(3, val)
        }
        // also filter map
        filterMap(mappy, $(this).find(":selected").attr("data"));
        
        window.spinner_map.stop();
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
	
	// The following have to use delegation from $("body") to cope with datatable page switching
	
	$("body").on("click", ".a-dl", function() {
	    e.preventDefault()
	    alert('not yet')
	})

	$("body").on("click", ".table-chk", function() {
		e.preventDefault()
		console.log('adding', $(this).data('id'))
		/*console.log('checked_rows',checked_rows)*/
	})

	$("body").on("click", "#placetable tbody tr", function() { 
		const ds_pid = $(this).data('ds_pid');
		
		// highlight this row, clear others
		var selected = $(this).hasClass("highlight-row");
		$("#placetable tr").removeClass("highlight-row");
	
		if (!selected)
			$(this).removeClass("rowhover");
		$(this).addClass("highlight-row");
		
		// fetch its detail
		getPlace(ds_pid.pid, spinner_detail);
		
		highlightFeature(ds_pid, features, mappy);
	
	});
			
	// Custom search function to filter table based on dateline.fromValue and dateline.toValue
	$.fn.dataTable.ext.search.push(function (settings, data, dataIndex) {
		if ( $('.range_container.expanded').length == 0) { // Is dateline inactive?
			return true;
		}
		
	    const fromValue = window.dateline.fromValue;
	    const toValue = window.dateline.toValue;
	    const includeUndated = window.dateline.includeUndated
	    
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
	
	return {table, checked_rows}
}