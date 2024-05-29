// pids generate new CollPlace (collection_collplace) and
// TraceAnnotation records (trace_annotation) for each pid

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// export function add_to_collection(coll, pids, checked_rows) {
export function add_to_collection(coll, checked_rows) {
	console.log('add_to_collection()', coll, checked_rows)
	var formData = new FormData()
	formData.append('collection', coll)
	formData.append('place_list', checked_rows)

	/* collection.views.add_places() */
	$.ajax({
		type: 'POST',
		enctype: 'multipart/form-data',
		url: '/collections/add_places/',
		headers: { 'X-CSRFToken': csrfToken },
		processData: false,
		contentType: false,
		cache: false,
		data: formData,
		success: function(response) {
			console.log('response', response)
			var dupes = response.msg.dupes
			var added = response.msg.added
			if (dupes.length > 0) {
				let msg = dupes.length + ' records ' + (dupes.length > 1 ? 'were' : "was") +
					' already in the collection: [' + dupes + ']';
				alert(msg)
			} else {
				// notify success & clear checks and list
				checked_rows.length = 0
				$("#added_flash").fadeIn().delay(2000).fadeOut()
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

function create_collection() {
	let title = $("#title_input").val()
	if (title != '') {
		// create new place collection, return id
		var formData = new FormData()
		formData.append('title', title)
		$.ajax({
			type: 'POST',
			enctype: 'multipart/form-data',
			url: '/collections/flash_create/',
			headers: { 'X-CSRFToken': csrfToken },
			processData: false,
			contentType: false,
			cache: false,
			data: formData,
			success: function(data) {
				el = $('<li><a class="a_addtocoll" href="#" ref=' + data.id + '>' + data.title + '</a></li>')
				el.click(function() {
					coll = data.id
					// pids = checked_rows
					// add_to_collection(coll, pids, checked_rows)
					add_to_collection(coll, checked_rows)
					console.log('checked_rows to coll', checked_rows, coll)
				})
				$("#my_collections").append(el)
			}
		})
		$("#title_form").hide()
	} else {
		alert('Your new collection needs a title!')
	}
}

export function init_collection_listeners(checked_rows) {
	
	// Used in `mapAndTable.js`
	$(".a_addtocoll").click(function() {
		let coll = $(this).attr('ref')
		// let pids = checked_rows
		// add_to_collection(coll, pids, checked_rows)
		add_to_collection(coll, checked_rows)
	})
	
}