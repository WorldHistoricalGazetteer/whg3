import './vis_parameters';

$(function() {

	$("#id_group option:first").text('None')

	$("#id_group").change(function() {
		if ($("#id_group").val() == "") {
			$("#btn_coll_update").attr('value', 'Withdraw')
			$("#submit_prompt").fadeOut()
		} else {
			$("#btn_coll_update").attr('value', 'Submit')
		}
		console.log('changed group setting')
	})

	$("#coll_placelist div:first-child").click()
	var cardList = $('#coll_placelist');
	/*var panelList = $('#draggablePanelList');*/
	cardList.sortable({
		// Only make the .panel-heading child elements support dragging.
		// Omit this to make then entire <li>...</li> draggable.
		/*handle: '.row-handle',*/
		axis: 'y',
		update: function(event, ui) {
			/*console.log('$(this)', $(this))*/
			/*console.log('$(elem)', $(elem))*/
			new_sequence = {}
			$('.col-place-card', cardList).each(function(index, elem) {
				id = $(elem).data('id')
				new_sequence[id] = index
				$("#" + id + " .seq-visible").text("id: " + id + "; seq: " + index)
			});
			// Persist the new indices.
			var formData = new FormData()
			formData.append('coll_id', object_id)
			formData.append('seq', JSON.stringify(new_sequence))
			formData.append('csrfmiddlewaretoken', csrf_token);
			$.ajax({
				type: 'POST',
				/*enctype: 'multipart/form-data',*/
				url: '{% url "collection:update-sequence" %}',
				processData: false,
				contentType: false,
				cache: false,
				data: formData,
				dataType: "json",
				async: false,
				success: function(result) {
					console.log('result', result)
				}
			});
		}
	})
	// TODO: change text depending on state
	// scroll to place w/last saved annotation
	let offset = sessionStorage.getItem('offset')
	$("#coll_placelist").scrollTop(offset)

	window.remove_these = []
	$("[rel='tooltip']").tooltip();
	$(".nav-link").click(function() {
		var tab = $(this).data('id')
		/*console.log(tab)*/
		if (tab == 'ds') {
			$("#coll_right_anno").addClass('hidden')
			/*$("#coll_right_intro").removeClass('hidden')*/
		} else {
			/*console.log('show anno header if there are place cards')*/
			if ($("#coll_placelist").children(".col-place-card").length > 0) {
				$("#coll_right_anno").removeClass('hidden')
			}
			/*$("#coll_right_intro").addClass('hidden')*/
		}
	})

	let dslist = []
	$(".textarea").each(function(index) {
		if (["None", "null"].includes($(this).val())) {
			$(this).val('')
		}
	});

	$("#id_geojson").attr("placeholder", "generated from country codes")

	// help modals
	$(".help-matches").click(function() {
		let page = $(this).data('id')
		/*console.log('help:', page)*/
		$('.selector').dialog('open');
	})

	$(".selector").dialog({
		resizable: false,
		autoOpen: false,
		height: $(window).height() * 0.9,
		width: $(window).width() * 0.8,
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

}) // end doc ready

$('#sharing_form').submit(function(event) {
	// Stop form from submitting normally
	event.preventDefault();
	console.log('sharing form submitted via ajax')

	var formData = new FormData(this);

	$.ajax({
		url: $(this).attr('action'),
		type: $(this).attr('method'),
		data: formData,
		processData: false,
		contentType: false,
		csrfmiddlewaretoken: csrf_token,
		success: function(response) {
			console.log('response', response)
			if (response.status == 'ok') {
				var removalMarkup = '<span class="float-end me-2"><a id="remove_collab" data-uid="' +
					response.uid + '" href="/collections/collab-remove/' + response.uid +
					'/' + response.cid + '/"><i class="fas fa-times-circle linky"></i></a></span>';
				$("#collabs_list").append(
					'<li>' + response.user + removalMarkup + '</li>')
				history.replaceState(null, null, '#coll_collaborators');
				$('.nav-link[data-bs-target="#coll_collaborators"]').tab('show');
				$('input[name="username"]').val('');
			} else {
				alert(response.status)
			}
		},
		error: function(response) {
			alert('a problem occurred')
		}
	});
});

// remove collaborator from collection
$(document).on('click', '#remove_collab', function(event) {
	event.preventDefault();
	console.log('remove collab')
	var uid = $(this).data('uid');
	var cid = '{{ object.id }}';

	$.ajax({
		url: '/collections/collab-remove/' + uid + '/' + cid + '/',
		type: 'POST',
		data: {
			'csrfmiddlewaretoken': csrf_token
		},
		success: function(response) {
			console.log('response', response)
			$('#remove_collab[data-uid="' + response.uid + '"]').parent().parent().remove();
			// Instead of setting window.location.hash directly, use history.replaceState()
			history.replaceState(null, null, '#coll_collaborators');
			$('.nav-link[data-bs-target="#coll_collaborators"]').tab('show');

		},
		error: function(response) {
			// Handle error
			console.log('error', response)
		}
	});
});

$("#check_submitter").click(function(e) {
	$("#submitter").toggle()
})

function showChooser(type) {
	elem = "#" + type + "_chooser"
	$(elem).toggle()
}

$("#btn_coll_submit").click(function(e) {
	e.preventDefault()
	group_connect('submit')
})
$("#btn_coll_unsubmit").click(function(e) {
	e.preventDefault()
	group_connect('unsubmit')
})

// flag collection as submitted, shows up on leader's list
function group_connect(action) {
	console.log('submitting collection {{ object.id }} to group ' + $("#id_group").val())
	var formData = new FormData()
	formData.append('action', action)
	formData.append('coll', '{{ object.id }}')
	formData.append('group', $("#id_group").val())
	formData.append('csrfmiddlewaretoken', csrf_token);
	$.ajax({
		type: 'POST',
		enctype: 'multipart/form-data',
		url: '{% url "collection:group-connect" %}',
		processData: false,
		contentType: false,
		cache: false,
		data: formData,
		success: function(response) {
			if (response.status == 'ok') {
				console.log(response)
			} else {
				console.log(response)
			}
		}
	})
}

/*function goBrowse() {*/
/*  window.location = '/collections/{{ object.id }}/browse_pl'*/
/* }*/

function saveExit() {
	$("#collection_form").submit()
}

// add link to collection
function create_collection_link() {
	var formData = new FormData()
	formData.append('model', 'Collection')
	formData.append('objectid', '{{ object.id }}')
	formData.append('uri', $("#l_uri").val())
	formData.append('label', $("#l_label").val())
	formData.append('link_type', $("#select_linktype").val())
	formData.append('license', '')
	formData.append('csrfmiddlewaretoken', csrf_token);
	$.ajax({
		type: 'POST',
		enctype: 'multipart/form-data',
		url: '{% url "create-link" %}',
		processData: false,
		contentType: false,
		cache: false,
		data: formData,
		success: function(response) {
			if (response.result == 'dupe') {
				alert('That url is already linked to this collection!')
			} else if (response.result == 'bad uri') {
				alert('That url is not formed correctly!')
			} else {
				linky = response.result
				console.log(linky)
				$("#linklist").append(linky.link_icon + ' <a href="' + linky.uri +
					'" target="_blank">' + linky.label + '</a>')
				$("#added_flash").fadeIn().delay(2000).fadeOut()
				if ($("#linklist svg").length >= 2) {
					$(".link-counter").html("(that's 3!)")
				}
				/*console.log('added! gimmee feedback', response.result)*/
			}
		}
	})
	/*$("#addtocoll").hide()*/
	$("#linkform_popup input").val('')
	$("#linkform_popup").hide()
}

$("#a_linkpopup").click(function() {
	$("#linkform_popup").fadeIn()
})

$("#b_createlink").click(function() {
	create_collection_link()
})

// do something with place name (modal popup?)
$(".coll-place").click(function() {
	/*console.log('place record', $(this).data('pid'));*/
})

/*$(".closer").click(function(){*/
/*		$(".pop").fadeOut()*/
/* })*/

$("#b_cancel_link").click(function() {
	$(".pop").fadeOut()
})

// remove places from collection (archiving annotations)
function remove_from_collection(coll, pids) {
	var formData = new FormData()
	formData.append('collection', coll)
	formData.append('place_list', pids)
	formData.append('csrfmiddlewaretoken', csrf_token);
	$.ajax({
		type: 'POST',
		enctype: 'multipart/form-data',
		url: '/collections/archive_traces/',
		processData: false,
		contentType: false,
		cache: false,
		data: formData,
		success: function(response) {
			/*console.log('result:', response)*/
		}
	})
	// remove card from dom & hide link
	$(".col-place-card").each(function(index) {
		if (remove_these.includes($(this).data('id'))) {
			$(this).remove()
		}
	})
	// update count in tab
	newcount = $(".col-place-card").length
	$("#place_count").text(newcount)
	remove_these = [];
	$("#a_remove").text('')
}

// remove place(s) from collection
$("#a_remove").click(function() {
	coll = '{{ object.id }}'
	remove_from_collection(coll, remove_these)
})

// mark/unmark place for removal from collection
$(".mark-place").click(function(e) {
	let card;
	e.stopPropagation()
	pid = $(this).data('pid')
	col = $(this).data('col')
	/*console.log('mark ' + pid + ' in ' + col)*/
	if (remove_these.indexOf(pid) > -1) {
		console.log('unmarked', pid)
		// unmark it
		card = $(".col-place-card[data-id=" + pid + "]")
		card.css('opacity', 1.0)
		$(".col-place-card[data-id=" + pid + "] i.fa-plus-circle")
			.addClass('fa-minus-circle')
			.removeClass('fa-plus-circle')
			.css('color', 'lightcoral')
		$(card[0]).find('.restore-place').addClass('remove-place')
			.removeClass('restore-place')
		idx = remove_these.indexOf(pid)
		remove_these.splice(idx, 1)
		$("#a_remove").html('remove ' + remove_these.length)
		if (remove_these.length == 0) {
			$("#a_remove").html('')
		}
	} else {
		// mark for removal
		console.log('marked', pid, 'added to remove_these')
		card = $(".col-place-card[data-id=" + pid + "]")
		card.css('opacity', 0.5)
		$(".col-place-card[data-id=" + pid + "] i.fa-minus-circle")
			.addClass('fa-plus-circle')
			.removeClass('fa-minus-circle')
			.css('color', 'green')
		$(card[0]).find('.remove-place').addClass('restore-place')
			.removeClass('remove-place')
		remove_these.push(pid)
		$("#a_remove").html('remove ' + remove_these.length)
	}
})

// show/hide editor-restricted options
// $("#editor_options").hide();
$('.show-hide').click(function(e) {
	$("#editor_options").slideToggle("fast");
	var val = $(this).html() == "↑" ? "↓" : "↑";
	/*var val = $(this).html() == "-" ? "+" : "-";*/
	$(this).hide().html(val).fadeIn("fast");
	/*$(this).hide().html(val).fadeIn("fast");*/
	e.preventDefault();
});

// builds link for external place record
function url_extplace(identifier) {
	// abbreviate links not in aliases.base_urls
	if (identifier.startsWith('http')) {
		let tag = identifier.replace(/.+\/\/|www.|\..+/g, '')
		link = '<a href="' + identifier + '" target="_blank">' + tag + '<i class="fas fa-external-link-alt linky"></i>,  </a>'
	} else {
		link = '<a href="" class="ext" data-target="#ext_site">' + identifier + '<i class="fas fa-external-link-alt linky"></i></a>, '
	}
	return link
}

// builds link for external placetype record
function url_exttype(type) {
	/*console.dir(type)*/
	link = ' <a href="#" class="exttab" data-id=' + type.identifier +
		'>(' + type.label.label + ' <i class="fas fa-external-link-alt linky"></i>)</a>'
	return link
}

// extent of timespan list
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

// return html for display
function parsePlace(data) {
	window.featdata = data
	trace = JSON.parse(data.traces).find(function(t) {
		return t.fields.collection = object_id
	})
	if (trace) {
		/*console.log('has trace for this collection', trace.fields)*/
		$("#anno_detail").html(JSON.stringify(trace.fields))
	} else {
		/*console.log('no trace for this collection')*/
	}

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

	// TITLE
	descrip = '<p><b>Title</b>: <span id="row_title" class="larger text-danger">' + data.title + '</span>'
	// NAME VARIANTS
	descrip += '<p class="scroll65"><b>Variants</b>: '
	for (n in data.names) {
		let name = data.names[n]
		descrip += '<p>' + name.toponym != '' ? name.toponym + '; ' : ''
	}
	// TYPES
	// may include sourceLabel:"" **OR** sourceLabels[{"label":"","lang":""},...]
	// console.log('data.types',data.types)
	//{"label":"","identifier":"aat:___","sourceLabels":[{"label":" ","lang":"en"}]}
	descrip += '</p><p><b>Types</b>: '
	typeids = ''
	for (t in data.types) {
		str = ''
		var type = data.types[t]
		/*console.log('type',type)*/
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

	// LINKS
	//
	descrip += '<p class="mb-0"><b>Links</b>: <i>original: </i>'
	close_count = added_count = related_count = 0
	html_close = html_added = html_related = ''
	if (data.links.length > 0) {
		links = data.links
		links_arr = onlyUnique(data.links)
		/*console.log('distinct data.links',links_arr)*/
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

	// DESCRIPTIONS
	// TODO: link description to identifier URI if present
	if (data.descriptions.length > 0) {
		val = data.descriptions[0]['value'].substring(0, 300)
		descrip += '<p><b>Description</b>: ' + (val.startsWith('http') ? '<a href="' + val + '" target="_blank">Link</a>' : val) +
			' ... </p>'
		//'<br/><span class="small red-bold">('+data.descriptions[0]['identifier']+')</span>
	}

	// CCODES
	//
	//if (data.ccodes.length > 0) {
	if (!!data.countries) {
		//console.log('data.countries',data.countries)
		descrip += '<p><b>Modern country bounds</b>: ' + data.countries.join(', ') + '</p>'
	}

	// MINMAX
	//
	//console.log('data.minmax',data.minmax)
	mm = data.minmax
	if (data.minmax && !(mm[0] == null && mm[1] == null)) {
		descrip += '<p><b>When</b>: earliest: ' + data.minmax[0] + '; latest: ' + data.minmax[1]
	}

	// TRACES
	trace = JSON.parse(data.traces).find(function(t) {
		return t.fields.collection = object_id
	})

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

function getAnno(pid) {
	//let coll_id = "{{ object.id }}"
	// traces.views.get_form()
	// returns TraceAnnotationForm; w/instance if trace_annotation record exists & not archived, else empty
	const url = "/collections/annoform/?c=" + object_id + "&p=" + pid
	fetch(url)
		.then(function(response) {
			return response.json();
		})
		.then(function(data) {
			const formContainer = document.querySelector("#annotator");
			formContainer.innerHTML = data.form;
			$("[rel='tooltip']").tooltip();
			$("#keyword_color").html('#keyword_color')
		})
}

$(".col-place-card").click(function() {
	// clear highlights
	$(".col-place-card").removeClass('card-highlight')
	// current index
	/*console.log('idx', $(this).data('idx'))*/
	// get pid
	let pid = $(this).data('id')
	/*console.log('clicked $(this), pid', $(this), pid)*/
	let card = $(this).addClass('card-highlight')
	// position of clicked card
	let cardtop = card.offset().top
	sessionStorage.setItem('cardtop', cardtop)
	// position of list scroller
	let scrolltop = $("#coll_placelist").scrollTop()
	sessionStorage.setItem('scrolltop', scrolltop)
	// permanent position of list on page
	let listtop = $("#coll_placelist").offset().top
	let offset = cardtop + scrolltop - listtop
	sessionStorage.setItem('offset', offset)
	/*console.log('offset',offset)*/
	/*console.log('cardtop, scrolltop, listtop',*/
	/*	  cardtop, scrolltop, listtop )*/
	getAnno(pid)
})

// add dataset to collection
$("#select_ds").change(function() {
	/*console.log('selected from list', $(this).val())*/
	$("further_explanation").hide()

	if ($("a.active").data('id') == 'pl' && place_list) {
		$("#col_right_anno").fadeIn()
	}
	addDataset('create')
})

// render dataset to html
function listDataset(d) {
	/*console.log('listing this:', d.title)*/
	dslist.push(d.id)
	$("#id_datasets [value=" + d.id + "]").attr("checked", "checked");
	coll_id = object_id
	card = '<div class="ds_card" id="card_' + d.id + '">' +
		'<p class="mb-0"><a href="#"><span class="ds_title">' + d.title + '</span></a> (' + d.label + '/' + d.id + ')</p>' +
		'<div class="ds_fields">' +
		'<p class="my-1"><b>Description</b>: ' + d.description + '</p>' +
		'<p class="my-1"><b>Create date</b>: ' + d.create_date.slice(0, 10) + '; <b># rows</b>: ' + d.numrows + '</p>' +
		'<p class="my-1"><a href="javascript:{ removeDataset(' + d.id + ') }">' +
		'<i class="fas fa-minus-square" style="color:#336699"></i> remove</a>' +
		'<span class="float-end"><a class="a_addplaces" href="javascript:{addPlaces(' + d.id + ')}">add all ' +
		d.numrows + ' places</a></span' +
		'</p></div></div>'
	$(".a_addplaces").click(function() {
		thisy = $(this)
		/*console.log('thisy', thisy)*/
	})
	$("#coll_dscards_create").append(card)
	// console.log(card)
}

// adds all dataset places to placelist
function addPlaces(dsid) {
	let url = "/collections/add_dsplaces/" + object_id + "/" + dsid
	// collection.views.add_dataset
	/*console.log('adding dataset w/o save',dsid, {{ object.id }}, url)*/
	document.location.href = url
	/*url = "{% url 'collection:add-ds' ds_id="+dsid+" coll_id=456 %}"*/
	/*document.location.href = url.replace('123', dsid).replace('456',{{ object.id }})*/
	/*)*/
	/*$("#collection_form").submit('remain')*/
}

// lists dataset on dropdown select
function addDataset(action) {
	/*console.log('selected', $("#select_ds").val())*/

	$.get("/collections/list_ds", {
			ds_id: $("#select_ds").val()
		},
		function(data) {
			// render to html
			listDataset(data)
			/*console.log('ds to list:',data)*/
			// append ds.id to form
		});
	// reset select
	$("#select_ds").val(0)
	$("#msg").html('').hide()
}

// clears dataset card (cancels add)
function clearDataset(dsid) {
	/*console.log('clear card for ds', dsid)*/
	$("#card_" + dsid).remove()
}

// removes dataset from collection
function removeDataset(dsid) {
	/*console.log('removing ' + dsid + 'from collection '+ "{{object.id}}")*/
	$("#id_datasets [value=" + dsid + "]").prop("checked", false);
	let idx = dslist.indexOf(dsid)
	dslist.splice(idx, dslist.length);
	card = "#card_" + dsid
	$(card).remove()
	if (dslist.length == 0) {
		$("#msg").html('None yet...').show()
	}
	/*console.log('removed '+dsid+' from dslist[] and dom')*/
	// reset select
	$("#select_ds").val(0)
}
