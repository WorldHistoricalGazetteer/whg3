// tableFunctions-extended.js

export function scrollToRowByProperty(table, propertyName, value) {
	const pageInfo = table.page.info();
	const rowDataArray = table.rows({ search: 'applied', order: 'current' }).data().toArray();

	// Fast in-memory search
	const rowIndex = rowDataArray.findIndex(row => row?.properties?.[propertyName] === value);
	if (rowIndex === -1) {
		console.warn(`No row found with ${propertyName} = ${value}`);
		return;
	}

	const targetPage = Math.floor(rowIndex / pageInfo.length);

	const highlightRow = () => {
		const visibleData = table.rows({ page: 'current' }).data().toArray();
		const visibleNodes = table.rows({ page: 'current' }).nodes();

		for (let i = 0; i < visibleData.length; i++) {
			if (visibleData[i]?.properties?.[propertyName] === value) {
				const rowNode = visibleNodes[i];
				if (rowNode) {
					rowNode.scrollIntoView({ behavior: 'smooth', block: 'center' });
					$(rowNode).trigger('click');
				}
				break;
			}
		}
	};

	// If already on the correct page, trigger immediately
	if (pageInfo.page === targetPage) {
		highlightRow();
	} else {
		table.one('draw', highlightRow);
		table.page(targetPage).draw(false);
	}
}
