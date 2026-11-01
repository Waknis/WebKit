// CI-only, never part of the fix: runs the real "Jump to Definition" callback from
// Views/ContextMenuUtilities.js, which this CI branch adds to Test.html, with stand-ins
// for the two things Test.html does not have: the native menu and the Sources tab.
TestPage.registerInitializer(function() {

class FakeContextMenu {
    constructor() { this.items = []; }
    appendItem(label, handler) { this.items.push({label, handler}); return {}; }
    appendCheckboxItem(label, handler) { this.items.push({label, handler}); return {}; }
    appendSubMenuItem(label) { let subMenu = new FakeContextMenu; this.items.push({label, subMenu}); return subMenu; }
    appendSeparator() { }
}
WI.ContextMenu = FakeContextMenu;

// Resolves to the location the real callback asked to show, or null if it did nothing.
window.runRealJumpToDefinition = async function runRealJumpToDefinition(node, timeout = 3000) {
    let contextMenu = new WI.ContextMenu;
    WI.appendContextMenuItemsForDOMNode(contextMenu, node, {disallowEditing: true, excludeLogElement: true, excludeRevealElement: true});

    let item = contextMenu.items.find((item) => item.label === "Jump to Definition");
    InspectorTest.expectThat(!!item, "The real menu should offer Jump to Definition.");
    if (!item)
        return null;

    return new Promise((resolve) => {
        let timer = setTimeout(() => {
            WI.showSourceCodeLocation = null;
            resolve(null);
        }, timeout);
        WI.showSourceCodeLocation = (location, options) => {
            clearTimeout(timer);
            WI.showSourceCodeLocation = null;
            resolve(location);
        };
        item.handler();
    });
};

// Resolves to the location the next WI.showSourceCodeLocation call asks to show, or null if there is none.
window.awaitShownLocation = function awaitShownLocation(timeout = 3000) {
    return new Promise((resolve) => {
        let timer = setTimeout(() => {
            WI.showSourceCodeLocation = null;
            resolve(null);
        }, timeout);
        WI.showSourceCodeLocation = (location, options) => {
            clearTimeout(timer);
            WI.showSourceCodeLocation = null;
            resolve(location);
        };
    });
};

// Logs every Inspector.inspect event, and where the object would lead if this caller also opted in to the fallback.
window.observeInspectEvents = function observeInspectEvents(targetNames) {
    let originalInspect = WI.InspectorObserver.prototype.inspect;
    WI.InspectorObserver.prototype.inspect = function(payload, hints) {
        InspectorTest.log(`Inspector.inspect delivered: type=${payload.type}, objectId=${payload.objectId}`);
        WI.RemoteObject.fromPayload(payload, WI.mainTarget).findFunctionSourceCodeLocation({deliveredOnTarget: true}).then((location) => {
            let description = location instanceof WI.SourceCodeLocation ? describeJump(location, targetNames) : String(location);
            InspectorTest.log(`if inspect opted in to the fallback: ${description}`);
        });
        return originalInspect.call(this, payload, hints);
    };
};

window.describeJump = function describeJump(location, targetNames) {
    if (!location)
        return "did nothing";
    let targetName = targetNames.get(location.sourceCode.target) || location.sourceCode.target.constructor.name;
    let fileName = location.sourceCode.url?.split("/").at(-1) || "(anonymous script)";
    return `jumped to ${fileName}:${location.lineNumber}:${location.columnNumber} on the ${targetName}`;
};

// What the RemoteObject helper alone reports, for classes where the callback did nothing.
window.describeHelperResult = async function describeHelperResult(node, targetNames) {
    let nodeObject = await WI.RemoteObject.resolveNode(node, "test");
    let constructorObject = await nodeObject.getProperty("constructor");

    let details = null;
    try {
        details = (await constructorObject.target.DebuggerAgent.getFunctionDetails(constructorObject.objectId)).details;
    } catch (error) {
        return `getFunctionDetails failed: ${error}`;
    }

    let result = await constructorObject.findFunctionSourceCodeLocation({deliveredOnTarget: true});
    let known = !!WI.debuggerManager.scriptForStackTraceIdentifier(details.location.scriptId, constructorObject.target, {deliveredOnTarget: true});
    let description = result instanceof WI.SourceCodeLocation ? describeJump(result, targetNames) : String(result);
    return `getFunctionDetails answered by ${targetNames.get(constructorObject.target) || constructorObject.target.constructor.name}, line ${details.location.lineNumber}, script known: ${known}; helper: ${description}`;
};

});
