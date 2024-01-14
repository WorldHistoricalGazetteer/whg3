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
export function add_to_collection(coll, pids) {
	console.log('add_to_collection()', coll, pids)
	var formData = new FormData()
	formData.append('collection', coll)
	formData.append('place_list', pids)

	var csrftoken = getCookie('csrftoken');
  	formData.append('csrfmiddlewaretoken', csrftoken);

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
			console.log('response', response)
			var dupes = response.msg.dupes
			var added = response.msg.added
			if (dupes.length > 0) {
				let msg = dupes.length + ' records ' + (dupes.length > 1 ? 'were' : "was") +
					' already in the collection: [' + dupes + ']';
				// if (added.length > 0) {
				// 	msg += ']; ' + added.length + ' ' + (added.length > 1 ? 'were' : "was") + ' added'
				// }
				alert(msg)
			} else {
				// notify success & clear checks and list
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

export function init_collection_listeners(checked_rows) {

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

	$("#create_coll_link").click(function() {
		console.log('open title input')
		$("#title_form").show()
	})

	$(".closer").click(function(){
      $(this).parent().hide()
	})

	// $("#addchecked").click(function(){
    //   $("#addtocoll_popup").fadeIn()
	// })

	// single pid for place portal; adapt for multi-select elsewhere
	$(".action:radio").click(function(){
			pid = $('input[name="r_anno"]:checked').data('id');
			console.log('checked radio for pid:', pid)
			$("#addtocoll").fadeIn()
			let checked_cards = []
			checked_cards.push($(this).data("id"))
	})

	// Used in ds_places.html publication page
	// Listen for table row click (assigned using event delegation to allow for redrawing)
	$("body").on("click", "#placetable tbody tr", function() {
		const thisy = $(this)
		// get id
		const pid = $(this)[0].cells[0].textContent
		// is checkbox checked?
		// if not, ensure row pid is not in checked_rows
		if (window.loggedin == true) {
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
	
	});



}