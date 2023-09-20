export function getPlace(pid, spinner_detail) {
	console.log('getPlace()', pid);
    if (isNaN(pid)) {
        console.log('Invalid pid');
        return;
    }
	$.ajax({
		url: "/api/place/" + pid,
	}).done(function(data) {
		$("#detail").html(parsePlace(data))
		if(spinner_detail) spinner_detail.stop()
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
				const matches = str.match(re);
				url = base_urls[matches[1]] + matches[2]
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
		let parent = '<p class="mb-0"><b>Parent(s)</b>: ';
		let related = '<p class="mb-0"><b>Related</b>: ';
		for (var r in data.related) {
			const rel = data.related[r]
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

function minmaxer(timespans) {
	//console.log('got to minmax()',JSON.stringify(timespans))-->
	let starts = [];
	let ends = []
	for (var t in timespans) {
		// gets 'in', 'earliest' or 'latest'
		starts.push(Object.values(timespans[t].start)[0])
		ends.push(!!timespans[t].end ? Object.values(timespans[t].end)[0] : -1)
	}
	//console.log('starts',starts,'ends',ends)-->
	return [Math.max.apply(null, starts), Math.max.apply(null, ends)]
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