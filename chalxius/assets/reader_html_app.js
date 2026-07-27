(function () {
  'use strict';

  const packet = JSON.parse(document.getElementById('chalxius-reader-packet').textContent);
  const buildMeta = JSON.parse(document.getElementById('chalxius-build-meta').textContent);
  const nodeById = new Map(packet.nodes.map((node, index) => [node.id, {...node, packetIndex: index}]));
  const edgeById = new Map(packet.edges.map((edge, index) => [edge.id, {...edge, packetIndex: index}]));
  const incomingEdgesByNode = new Map(packet.nodes.map((node) => [node.id, []]));
  const outgoingEdgesByNode = new Map(packet.nodes.map((node) => [node.id, []]));
  for (const edge of edgeById.values()) {
    incomingEdgesByNode.get(edge.target).push(edge);
    outgoingEdgesByNode.get(edge.source).push(edge);
  }
  const themeById = new Map(packet.themes.map((theme) => [theme.id, theme]));
  const themeOrderIndex = new Map(packet.theme_order.map((id, index) => [id, index]));
  const targetOrderIndex = new Map(packet.target_order.map((id, index) => [id, index]));
  const groupedThemeIds = packet.theme_order.filter((themeId) => themeById.get(themeId).target_ids.length > 1);
  const readerNodeIds = packet.nodes.map((node) => node.id);

  const state = {
    locale: 'zh',
    minimizedNodeIds: new Set(packet.nodes.filter((node) => node.reader_role !== 'target').map((node) => node.id)),
    sizingUndoStack: [],
    sizingRedoStack: [],
    appearanceScheme: 'faceted',
    includeResearch: false,
    includeLearning: false,
    includeReader: false,
    includeWeak: false,
    pinned: new Map(),
    selectedId: null,
    searchMatches: [],
    contextNodeId: null,
    hoveredCanvasNodeId: null,
    hoveredControlNodeId: null,
    hoveredNodeId: null,
    tooltipNodeId: null,
    detailWidth: 384,
    detailScale: 100,
    contextReturnFocus: null
  };
  let windowResizeTimer = null;
  let nodeControlFrame = 0;
  let nodeHoverFrame = 0;
  const CANONICAL_COLUMN_SPACING = 340;
  const NODE_SIZE_CONTROL_X_RATIO = 0.29;
  const NODE_SIZE_CONTROL_Y_RATIO = 0.5;
  const NODE_SIZE_CONTROL_CARD_HEIGHT_RATIO = 0.45;
  const NODE_SIZE_CONTROL_MAX_PX = 20;
  const NODE_SIZE_CONTROL_MIN_PX = 11;
  const NODE_CONTROL_SAFE_MIN_ZOOM = 0.36;
  const CROSSING_REDUCTION_SWEEPS = 8;
  const CROSSING_REDUCTION_EDGE_LIMIT = 1200;
  const COMPACT_NODE_SIZES = Object.freeze({
    target: {width: 78, height: 46},
    definition: {width: 80, height: 44},
    result: {width: 76, height: 44},
    explanation: {width: 74, height: 44}
  });
  const SIZE_HISTORY_LIMIT = 100;

  const elements = [];
  for (const themeId of groupedThemeIds) {
    const theme = themeById.get(themeId);
    elements.push({
      group: 'nodes',
      data: {
        id: `reader-theme:${themeId}`,
        kind: 'theme',
        label: themeDisplayLabel(theme),
        themeId
      },
      grabbable: true,
      selectable: true,
      position: {x: 0, y: 0}
    });
    for (const targetId of theme.target_ids) {
      elements.push({
        group: 'edges',
        data: {
          id: `reader-group:${themeId}:${targetId}`,
          source: `reader-theme:${themeId}`,
          target: targetId,
          kind: 'reader-grouping',
          category: 'reader-grouping',
          weak: 'no',
          layer: 'presentation'
        },
        selectable: false
      });
    }
  }
  for (const node of packet.nodes) {
    elements.push({
      group: 'nodes',
      data: {
        id: node.id,
        kind: 'reader-node',
        label: nodeDisplayLabel(node),
        title: node.title,
        role: node.reader_role,
        plane: node.plane,
        visualStatus: node.visual_status,
        layer: node.layer,
        themeId: node.theme_id,
        minimized: node.reader_role === 'target' ? 'no' : 'yes'
      },
      position: {x: 0, y: 0}
    });
  }
  for (const edge of packet.edges) {
    elements.push({
      group: 'edges',
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        category: edge.category,
        relation: edge.relation,
        exactType: edge.exact_type,
        kind: 'reader-edge',
        weak: edge.weak ? 'yes' : 'no',
        layer: edge.layer
      }
    });
  }

  const cy = cytoscape({
    container: document.getElementById('cy'),
    elements,
    layout: {name: 'preset', fit: false},
    minZoom: NODE_CONTROL_SAFE_MIN_ZOOM,
    maxZoom: 3.2,
    boxSelectionEnabled: false,
    selectionType: 'single',
    style: [
      {
        selector: 'node[kind = "reader-node"]',
        style: {
          'width': 190,
          'height': 72,
          'padding': 9,
          'background-color': '#111e2b',
          'border-color': '#536579',
          'border-width': 2,
          'border-style': 'solid',
          'color': '#e8eef5',
          'font-family': 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
          'font-size': 13,
          'font-weight': 500,
          'label': 'data(label)',
          'text-wrap': 'wrap',
          'text-max-width': 142,
          'text-valign': 'center',
          'text-halign': 'center',
          'text-justification': 'left',
          'overlay-padding': 9,
          'overlay-opacity': 0,
          'transition-property': 'border-color, border-width, opacity',
          'transition-duration': '0ms'
        }
      },
      { selector: 'node[plane = "fact"]', style: {'background-color': '#102a33', 'border-color': '#26c7cc'} },
      { selector: 'node[plane = "paper"]', style: {'background-color': '#2b2518', 'border-color': '#d0aa63'} },
      { selector: 'node[plane = "audit"]', style: {'background-color': '#251d32', 'border-color': '#9a70d1'} },
      { selector: 'node[plane = "blackboard"]', style: {'background-color': '#18222d', 'border-color': '#718095'} },
      { selector: 'node[plane = "learning"]', style: {'background-color': '#152a20', 'border-color': '#7fdd89'} },
      { selector: 'node[plane = "reader"]', style: {'background-color': '#12282a', 'border-color': '#63d7ad'} },
      { selector: 'node[role = "target"]', style: {'border-width': 3.5, 'width': 236, 'height': 100, 'text-max-width': 106, 'text-margin-x': 18} },
      { selector: 'node[role = "definition"]', style: {'width': 228, 'height': 92, 'text-max-width': 102, 'text-margin-x': 18} },
      { selector: 'node[role = "result"]', style: {'width': 220, 'height': 88, 'text-max-width': 98, 'text-margin-x': 17} },
      { selector: 'node[role = "explanation"]', style: {'width': 208, 'height': 84, 'text-max-width': 92, 'text-margin-x': 17} },
      {
        selector: 'node.shape-faceted[role = "target"]',
        style: {
          'shape': 'polygon',
          'shape-polygon-points': [-0.76, -1, 0.76, -1, 1, -0.56, 1, 0.56, 0.76, 1, -0.76, 1, -1, 0.56, -1, -0.56],
          'border-join': 'round'
        }
      },
      {
        selector: 'node.shape-faceted[role = "definition"]',
        style: {
          'shape': 'polygon',
          'shape-polygon-points': [0, -1, 1, 0, 0, 1, -1, 0],
          'border-join': 'round'
        }
      },
      {
        selector: 'node.shape-faceted[role = "result"]',
        style: {
          'shape': 'polygon',
          'shape-polygon-points': [-0.72, -1, 0.72, -1, 1, 0, 0.72, 1, -0.72, 1, -1, 0],
          'border-join': 'round'
        }
      },
      {
        selector: 'node.shape-faceted[role = "explanation"]',
        style: {
          'shape': 'polygon',
          'shape-polygon-points': [-0.82, -1, 0.82, -1, 1, -0.58, 1, 0.58, 0.82, 1, -0.82, 1, -1, 0.58, -1, -0.58],
          'border-join': 'round'
        }
      },
      {
        selector: 'node.shape-plaques',
        style: {
          'border-style': 'solid',
          'border-position': 'inside',
          'border-width': 1.35,
          'border-opacity': 0.34,
          'outline-style': 'solid',
          'outline-width': 1.8,
          'outline-offset': 2.4,
          'outline-opacity': 0.92
        }
      },
      { selector: 'node.shape-plaques[plane = "fact"]', style: {'outline-color': '#26c7cc'} },
      { selector: 'node.shape-plaques[plane = "paper"]', style: {'outline-color': '#d0aa63'} },
      { selector: 'node.shape-plaques[plane = "audit"]', style: {'outline-color': '#9a70d1'} },
      { selector: 'node.shape-plaques[plane = "blackboard"]', style: {'outline-color': '#718095'} },
      { selector: 'node.shape-plaques[plane = "learning"]', style: {'outline-color': '#7fdd89'} },
      { selector: 'node.shape-plaques[plane = "reader"]', style: {'outline-color': '#63d7ad'} },
      {
        selector: 'node.shape-plaques[role = "target"]',
        style: {
          'shape': 'polygon',
          'shape-polygon-points': [-0.82, -1, 0.82, -1, 0.82, -0.90, 0.94, -0.90, 0.94, -0.72, 1, -0.72, 1, 0.72, 0.94, 0.72, 0.94, 0.90, 0.82, 0.90, 0.82, 1, -0.82, 1, -0.82, 0.90, -0.94, 0.90, -0.94, 0.72, -1, 0.72, -1, -0.72, -0.94, -0.72, -0.94, -0.90, -0.82, -0.90],
          'border-join': 'round'
        }
      },
      { selector: 'node.shape-plaques[role = "definition"]', style: {'shape': 'round-rectangle', 'border-join': 'round'} },
      {
        selector: 'node.shape-plaques[role = "result"]',
        style: {
          'shape': 'polygon',
          'shape-polygon-points': [-0.88, -1, 0.88, -1, 0.88, -0.82, 1, -0.82, 1, 0.82, 0.88, 0.82, 0.88, 1, -0.88, 1, -0.88, 0.82, -1, 0.82, -1, -0.82, -0.88, -0.82],
          'border-join': 'round'
        }
      },
      {
        selector: 'node.shape-plaques[role = "explanation"]',
        style: {
          'shape': 'polygon',
          'shape-polygon-points': [-1, -1, 0.72, -1, 1, -0.46, 1, 1, -1, 1],
          'border-join': 'round'
        }
      },
      { selector: 'node.minimized', style: {'padding': 0, 'label': '', 'text-opacity': 0, 'text-margin-x': 0, 'border-width': 2.4} },
      { selector: 'node.minimized[role = "target"]', style: {'width': 78, 'height': 46} },
      { selector: 'node.minimized[role = "definition"]', style: {'width': 80, 'height': 44} },
      { selector: 'node.minimized[role = "result"]', style: {'width': 76, 'height': 44} },
      { selector: 'node.minimized[role = "explanation"]', style: {'width': 74, 'height': 44} },
      { selector: 'node.shape-plaques.minimized', style: {'border-width': 1.1, 'border-opacity': 0.3, 'outline-width': 1.4, 'outline-offset': 1.4, 'outline-opacity': 0.78} },
      { selector: 'node[visualStatus = "research"]', style: {'border-style': 'dashed'} },
      { selector: 'node[visualStatus = "challenged"]', style: {'border-color': '#d16aa1', 'border-width': 5} },
      { selector: 'node[visualStatus = "inactive"]', style: {'opacity': 0.36, 'border-style': 'dotted'} },
      { selector: 'node.shape-plaques[visualStatus = "research"]', style: {'outline-style': 'dashed'} },
      { selector: 'node.shape-plaques[visualStatus = "challenged"]', style: {'border-color': '#d16aa1', 'border-width': 1.5, 'outline-color': '#d16aa1', 'outline-width': 2.2, 'outline-opacity': 1} },
      { selector: 'node.shape-plaques[visualStatus = "inactive"]', style: {'outline-style': 'dotted', 'outline-opacity': 0.46} },
      {
        selector: 'node[kind = "theme"]',
        style: {
          'shape': 'round-rectangle',
          'width': 178,
          'height': 48,
          'background-color': '#0f1d2a',
          'border-color': '#326778',
          'border-style': 'dashed',
          'border-width': 1.4,
          'color': '#c0cbd8',
          'font-family': 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
          'font-size': 12,
          'font-weight': 600,
          'label': 'data(label)',
          'text-wrap': 'wrap',
          'text-max-width': 158,
          'text-valign': 'center'
        }
      },
      {
        selector: 'edge',
        style: {
          'curve-style': 'bezier',
          'width': 2.6,
          'line-color': '#4f93ed',
          'line-style': 'solid',
          'mid-target-arrow-color': '#4f93ed',
          'mid-target-arrow-shape': 'triangle',
          'target-arrow-color': '#4f93ed',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 1.65,
          'opacity': 0.84,
          'overlay-padding': 8,
          'overlay-opacity': 0
        }
      },
      {
        selector: 'edge[layer = "research"]',
        style: {
          'line-style': 'dashed',
          'line-dash-pattern': [10, 6]
        }
      },
      {
        selector: 'edge[category = "support"]',
        style: {
          'width': 4,
          'line-color': '#7fdd89',
          'mid-target-arrow-color': '#7fdd89',
          'mid-target-arrow-shape': 'vee',
          'target-arrow-color': '#7fdd89',
          'target-arrow-shape': 'vee'
        }
      },
      {
        selector: 'edge[category = "repair"]',
        style: {
          'line-color': '#d0aa63',
          'line-style': 'dashed',
          'line-dash-pattern': [10, 6],
          'mid-target-arrow-color': '#d0aa63',
          'mid-target-arrow-shape': 'diamond',
          'mid-target-arrow-fill': 'hollow',
          'target-arrow-color': '#d0aa63',
          'target-arrow-shape': 'diamond',
          'target-arrow-fill': 'hollow'
        }
      },
      {
        selector: 'edge[category = "conflict"]',
        style: {
          'line-color': '#d16aa1',
          'line-style': 'dotted',
          'mid-target-arrow-color': '#d16aa1',
          'mid-target-arrow-shape': 'tee',
          'target-arrow-color': '#d16aa1',
          'target-arrow-shape': 'tee'
        }
      },
      { selector: 'edge[weak = "yes"]', style: {'opacity': 0.42, 'width': 1.6} },
      {
        selector: 'edge[kind = "reader-grouping"]',
        style: {
          'curve-style': 'bezier',
          'width': 2,
          'line-color': '#4f7464',
          'line-style': 'dashed',
          'line-dash-pattern': [7, 5],
          'mid-target-arrow-shape': 'none',
          'target-arrow-color': '#4f7464',
          'target-arrow-shape': 'none',
          'opacity': 0.78,
          'events': 'no'
        }
      },
      { selector: 'edge.compact-edge', style: {'opacity': 0.2} },
      { selector: 'edge.edge-dim', style: {'opacity': 0.11} },
      { selector: 'edge.edge-related', style: {'opacity': 1} },
      { selector: 'edge.edge-related[weak = "yes"]', style: {'opacity': 0.62} },
      { selector: 'edge[kind = "reader-grouping"].edge-dim', style: {'opacity': 0.18} },
      { selector: 'edge[kind = "reader-grouping"].edge-related', style: {'opacity': 0.78} },
      { selector: '.hidden', style: {'display': 'none'} },
      { selector: 'edge:selected', style: {'width': 6, 'opacity': 1} },
      { selector: '.search-match', style: {'underlay-color': '#26c7cc', 'underlay-opacity': 0.2, 'underlay-padding': 10} },
      { selector: '.theme-member', style: {'underlay-color': '#7fdd89', 'underlay-opacity': 0.16, 'underlay-padding': 12} },
      { selector: '.context-node', style: {'underlay-color': '#7fdd89', 'underlay-opacity': 0.2, 'underlay-padding': 14} },
      {
        selector: 'node:selected',
        style: {
          'outline-color': '#ffe58a',
          'outline-style': 'solid',
          'outline-width': 3,
          'outline-offset': 2.6,
          'outline-opacity': 1,
          'z-index': 999
        }
      },
      { selector: 'node.minimized:selected', style: {'outline-width': 2.4, 'outline-offset': 1.6} }
    ]
  });

  const dom = {
    title: document.getElementById('map-title'),
    subtitle: document.getElementById('map-subtitle'),
    audience: document.getElementById('map-audience'),
    snapshot: document.getElementById('map-snapshot'),
    introduction: document.getElementById('map-introduction'),
    auditBanner: document.getElementById('audit-banner'),
    viewDescription: document.getElementById('view-description'),
    detail: document.getElementById('map-detail'),
    detailTitle: document.getElementById('detail-title'),
    detailBadges: document.getElementById('detail-badges'),
    detailReadable: document.getElementById('detail-readable'),
    detailFormal: document.getElementById('detail-formal'),
    formalDetails: document.getElementById('formal-details'),
    overview: document.getElementById('overview-button'),
    allCards: document.getElementById('all-cards-button'),
    layerMenuButton: document.getElementById('layer-menu-button'),
    layerPopover: document.getElementById('layer-popover'),
    fit: document.getElementById('fit-view-button'),
    reset: document.getElementById('reset-layout-button'),
    reloadGraph: document.getElementById('reload-graph-button'),
    undoSizing: document.getElementById('undo-sizing-button'),
    redoSizing: document.getElementById('redo-sizing-button'),
    headerOverview: document.getElementById('header-overview-button'),
    previousTarget: document.getElementById('previous-target-button'),
    nextTarget: document.getElementById('next-target-button'),
    targetPosition: document.getElementById('target-position'),
    canvasStage: document.querySelector('.canvas-stage'),
    cy: document.getElementById('cy'),
    selectedNodeHalo: document.getElementById('selected-node-halo'),
    nodeControlLayer: document.getElementById('node-control-layer'),
    nodeNameTooltip: document.getElementById('node-name-tooltip'),
    nodeContextMenu: document.getElementById('node-context-menu'),
    nodeContextMenuTitle: document.getElementById('node-context-menu-title'),
    contextCommands: [...document.querySelectorAll('[data-context-command]')],
    detailResizer: document.getElementById('detail-resizer'),
    detailTextSize: document.getElementById('detail-text-size'),
    detailTextSizeValue: document.getElementById('detail-text-size-value'),
    resetUi: document.getElementById('reset-ui-button'),
    localeChoices: [...document.querySelectorAll('[data-locale-choice]')],
    appearanceChoices: [...document.querySelectorAll('[data-appearance-scheme]')],
    research: document.getElementById('research-toggle'),
    learning: document.getElementById('learning-toggle'),
    reader: document.getElementById('reader-toggle'),
    weak: document.getElementById('weak-toggle'),
    search: document.getElementById('map-search'),
    searchStatus: document.getElementById('search-status'),
    copyBuild: document.getElementById('copy-build-button')
  };

  populatePageHeader();
  renderAuditBanner();
  bindEvents();
  Object.defineProperty(window, '__CHALXIUS_READER__', {
    value: Object.freeze({cy, state, packet, buildMeta}),
    enumerable: false,
    configurable: false,
    writable: false
  });
  applyStaticLocale();
  applyAppearanceScheme(state.appearanceScheme);
  showOverview();

  function planeLabel(plane) {
    const labels = {
      fact: bi('事实', 'Fact'), paper: bi('论文', 'Paper'), audit: bi('审计', 'Audit'),
      blackboard: bi('黑板', 'Blackboard'), learning: bi('学习', 'Learning'),
      reader: bi('读者注', 'Reader note')
    };
    return labels[plane] || plane.toUpperCase();
  }

  function roleLabel(role) {
    const labels = {
      target: bi('目标', 'Target'), definition: bi('定义', 'Definition'),
      result: bi('结果', 'Result'), explanation: bi('解释', 'Explanation')
    };
    return labels[role] || role;
  }

  function bi(zh, en) {
    return state.locale === 'zh' ? zh : en;
  }

  function themeDisplayLabel(theme) {
    return `${bi('主题', 'Topic')}\n${theme.label}`;
  }

  function nodeDisplayLabel(node) {
    const topic = themeById.get(node.theme_id);
    const orderPrefix = node.reader_role === 'target'
      ? `${targetOrderIndex.get(node.id) + 1}. `
      : '';
    const topicLine = node.reader_role === 'target' && topic && topic.target_ids.length === 1
      ? `\n${bi('主题', 'Topic')} · ${topic.label}`
      : '';
    return `${orderPrefix}${node.title}${topicLine}\n${roleLabel(node.reader_role)} · ${planeLabel(node.plane)}`;
  }

  function populatePageHeader() {
    document.title = `${packet.title} — ${bi('Chalxius 阅读器', 'Chalxius reader')}`;
    dom.title.textContent = packet.title;
    dom.subtitle.textContent = packet.presentation.subtitle;
    dom.audience.textContent = packet.audience;
    dom.snapshot.textContent = packet.source_snapshot.id;
    dom.snapshot.title = packet.source_snapshot.description;
    dom.introduction.textContent = packet.presentation.introduction;
  }

  function applyStaticLocale() {
    document.documentElement.lang = state.locale === 'zh' ? 'zh-CN' : 'en';
    document.documentElement.dataset.locale = state.locale;
    for (const element of document.querySelectorAll('[data-zh][data-en]')) {
      element.textContent = state.locale === 'zh' ? element.dataset.zh : element.dataset.en;
    }
    for (const element of document.querySelectorAll('[data-placeholder-zh][data-placeholder-en]')) {
      element.placeholder = state.locale === 'zh'
        ? element.getAttribute('data-placeholder-zh')
        : element.getAttribute('data-placeholder-en');
    }
    for (const element of document.querySelectorAll('[data-aria-label-zh][data-aria-label-en]')) {
      element.setAttribute(
        'aria-label',
        state.locale === 'zh'
          ? element.getAttribute('data-aria-label-zh')
          : element.getAttribute('data-aria-label-en')
      );
    }
    for (const element of document.querySelectorAll('[data-tooltip-zh][data-tooltip-en]')) {
      element.dataset.tooltip = state.locale === 'zh'
        ? element.dataset.tooltipZh
        : element.dataset.tooltipEn;
    }
    for (const button of dom.localeChoices) {
      button.setAttribute('aria-pressed', button.dataset.localeChoice === state.locale ? 'true' : 'false');
    }
  }

  function applyLocale(locale) {
    if (!['zh', 'en'].includes(locale) || state.locale === locale) return;
    const previousScrollTop = dom.detail.scrollTop;
    const previousFormalOpen = dom.formalDetails.open;
    const previousNestedDisclosure = [...dom.detailFormal.querySelectorAll('details')]
      .map((details) => details.open);
    state.locale = locale;
    applyStaticLocale();
    populatePageHeader();
    renderAuditBanner();
    cy.batch(() => {
      for (const themeId of groupedThemeIds) {
        cy.getElementById(`reader-theme:${themeId}`).data('label', themeDisplayLabel(themeById.get(themeId)));
      }
      for (const node of packet.nodes) cy.getElementById(node.id).data('label', nodeDisplayLabel(node));
    });
    refreshLocalizedDetail();
    dom.formalDetails.open = previousFormalOpen;
    [...dom.detailFormal.querySelectorAll('details')].forEach((details, index) => {
      details.open = Boolean(previousNestedDisclosure[index]);
    });
    updateViewDescription();
    updateButtons();
    updateNavigation();
    updateSearch();
    renderNodeControls();
    updateContextMenuCommands();
    dom.detail.scrollTop = previousScrollTop;
  }

  function applyAppearanceScheme(scheme) {
    if (!['faceted', 'plaques'].includes(scheme)) return;
    state.appearanceScheme = scheme;
    document.documentElement.dataset.appearanceScheme = scheme;
    cy.batch(() => {
      allReaderNodes().removeClass('shape-faceted shape-plaques');
      allReaderNodes().addClass(`shape-${scheme}`);
    });
    for (const button of dom.appearanceChoices) {
      button.setAttribute('aria-pressed', button.dataset.appearanceScheme === scheme ? 'true' : 'false');
    }
    scheduleNodeControlSync();
  }

  function refreshLocalizedDetail() {
    if (typeof state.selectedId === 'string' && state.selectedId.startsWith('reader-theme:')) {
      showThemeDetail(state.selectedId.slice('reader-theme:'.length));
    } else if (edgeById.has(state.selectedId)) {
      showEdgeDetail(state.selectedId);
    } else if (nodeById.has(state.selectedId)) {
      showNodeDetail(state.selectedId);
    } else {
      showOverviewDetail();
    }
  }

  function renderAuditBanner() {
    const hasNotice = !packet.audit.current_ok || packet.audit.warnings.length || packet.audit.unresolved.length;
    dom.auditBanner.replaceChildren();
    dom.auditBanner.classList.toggle('visible', Boolean(hasNotice));
    if (!hasNotice) return;
    const summary = document.createElement('p');
    summary.textContent = packet.audit.summary;
    dom.auditBanner.append(summary);
    const allItems = [
      ...packet.audit.warnings.map((text) => `${bi('警告', 'Warning')}: ${text}`),
      ...packet.audit.unresolved.map((text) => `${bi('未解决', 'Unresolved')}: ${text}`)
    ];
    if (allItems.length) {
      const details = document.createElement('details');
      const heading = document.createElement('summary');
      heading.textContent = bi(
        `${allItems.length} 条来源备注`,
        `${allItems.length} source note${allItems.length === 1 ? '' : 's'}`
      );
      const list = document.createElement('ul');
      for (const item of allItems) {
        const li = document.createElement('li');
        li.textContent = item;
        list.append(li);
      }
      details.append(heading, list);
      dom.auditBanner.append(details);
    }
  }

  function bindEvents() {
    for (const button of dom.localeChoices) {
      button.addEventListener('click', () => applyLocale(button.dataset.localeChoice));
    }
    for (const button of dom.appearanceChoices) {
      button.addEventListener('click', () => applyAppearanceScheme(button.dataset.appearanceScheme));
    }
    dom.overview.addEventListener('click', maximizeTargets);
    dom.allCards.addEventListener('click', maximizeAllCards);
    dom.headerOverview.addEventListener('click', maximizeTargets);
    dom.previousTarget.addEventListener('click', () => navigateTarget(-1));
    dom.nextTarget.addEventListener('click', () => navigateTarget(1));
    dom.undoSizing.addEventListener('click', undoSizing);
    dom.redoSizing.addEventListener('click', redoSizing);
    dom.layerMenuButton.addEventListener('click', (event) => {
      event.stopPropagation();
      const opening = dom.layerPopover.hidden;
      dom.layerPopover.hidden = !opening;
      dom.layerMenuButton.setAttribute('aria-expanded', opening ? 'true' : 'false');
    });
    dom.fit.addEventListener('click', fitVisible);
    dom.reset.addEventListener('click', () => {
      state.pinned.clear();
      resetCurrentLayout();
    });
    dom.reloadGraph.addEventListener('click', () => window.location.reload());
    dom.detailTextSize.addEventListener('input', () => {
      applyDetailScale(Number(dom.detailTextSize.value));
    });
    dom.resetUi.addEventListener('click', resetUi);
    bindDetailResizer();
    dom.research.addEventListener('change', () => {
      state.includeResearch = dom.research.checked;
      refreshForLayerChange();
    });
    dom.learning.addEventListener('change', () => {
      state.includeLearning = dom.learning.checked;
      refreshForLayerChange();
    });
    dom.reader.addEventListener('change', () => {
      state.includeReader = dom.reader.checked;
      refreshForLayerChange();
    });
    dom.weak.addEventListener('change', () => {
      state.includeWeak = dom.weak.checked;
      refreshForLayerChange();
    });
    dom.search.addEventListener('input', updateSearch);
    dom.search.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && state.searchMatches.length) {
        event.preventDefault();
        openSearchMatch(state.searchMatches[0]);
      }
    });
    window.addEventListener('resize', () => {
      resizeGraphPreservingViewport();
      window.clearTimeout(windowResizeTimer);
      windowResizeTimer = window.setTimeout(ensureGraphContentVisible, 120);
    });
    dom.copyBuild.addEventListener('click', async () => {
      await copyText(JSON.stringify(buildMeta, null, 2), dom.copyBuild);
    });
    cy.on('tap', 'node', (event) => {
      closeNodeContextMenu();
      const id = event.target.id();
      if (id.startsWith('reader-theme:')) {
        cy.elements().unselect();
        event.target.select();
        showThemeDetail(event.target.data('themeId'));
        return;
      }
      const node = nodeById.get(id);
      if (!node) return;
      showNodeDetail(id);
    });
    cy.on('dbltap', 'node[kind = "reader-node"]', (event) => {
      closeNodeContextMenu();
      maximizeNodePath(event.target.id());
    });
    cy.on('dbltap', 'node[kind = "theme"]', (event) => {
      closeNodeContextMenu();
      cy.elements().unselect();
      event.target.select();
      maximizeThemePath(event.target.data('themeId'));
    });
    cy.on('mouseover', 'node[kind = "reader-node"]', (event) => {
      state.hoveredCanvasNodeId = event.target.id();
      scheduleNodeHoverSync();
    });
    cy.on('mouseout', 'node[kind = "reader-node"]', (event) => {
      if (state.hoveredCanvasNodeId === event.target.id()) {
        state.hoveredCanvasNodeId = null;
      }
      scheduleNodeHoverSync();
    });
    cy.on('tap', (event) => {
      if (event.target !== cy) return;
      closeNodeContextMenu();
      hideNodeNameTooltip();
      showOverviewDetail();
      updateNavigation();
      renderNodeControls();
    });
    cy.on('cxttap', 'node[kind = "reader-node"]', (event) => {
      if (event.originalEvent && event.originalEvent.preventDefault) event.originalEvent.preventDefault();
      openNodeContextMenu(event.target.id(), event.renderedPosition || event.target.renderedPosition());
    });
    cy.on('tap', 'edge', (event) => {
      closeNodeContextMenu();
      if (event.target.data('kind') === 'reader-grouping') return;
      showEdgeDetail(event.target.id());
    });
    cy.on('dragfree', 'node', (event) => {
      const node = event.target;
      state.pinned.set(node.id(), {...node.position()});
      scheduleNodeControlSync();
    });
    cy.on('pan zoom position render resize', scheduleNodeControlSync);
    cy.on('pan zoom drag', () => {
      closeNodeContextMenu();
      hideNodeNameTooltip();
    });
    dom.cy.addEventListener('contextmenu', (event) => event.preventDefault());
    bindTrackpadNavigation();
    for (const button of dom.contextCommands) {
      button.addEventListener('click', () => runContextCommand(button.dataset.contextCommand));
    }
    dom.nodeContextMenu.addEventListener('keydown', handleContextMenuKeydown);
    document.addEventListener('pointerdown', (event) => {
      if (!dom.nodeContextMenu.hidden && !dom.nodeContextMenu.contains(event.target)) closeNodeContextMenu();
      if (!dom.layerPopover.hidden && !dom.layerPopover.contains(event.target) && event.target !== dom.layerMenuButton) {
        closeLayerPopover();
      }
    });
    document.addEventListener('keydown', (event) => {
      const tag = document.activeElement && document.activeElement.tagName;
      const editing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
        || Boolean(document.activeElement && document.activeElement.isContentEditable);
      const modifier = event.metaKey || event.ctrlKey;
      if (modifier && !event.altKey && !editing && event.key.toLocaleLowerCase('en') === 'z') {
        event.preventDefault();
        if (event.shiftKey) redoSizing();
        else undoSizing();
        return;
      }
      if (event.ctrlKey && !event.metaKey && !event.altKey && !editing && event.key.toLocaleLowerCase('en') === 'y') {
        event.preventDefault();
        redoSizing();
        return;
      }
      if (event.key === '/' && !editing) {
        event.preventDefault();
        dom.search.focus();
        return;
      }
      if ((event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) && nodeById.has(state.selectedId)) {
        event.preventDefault();
        const selected = cy.getElementById(state.selectedId);
        openNodeContextMenu(state.selectedId, selected.renderedPosition(), {focusMenu: true});
        return;
      }
      if (event.key !== 'Escape') return;
      if (!dom.nodeContextMenu.hidden) {
        closeNodeContextMenu({restoreFocus: true});
      } else if (!dom.layerPopover.hidden) {
        closeLayerPopover();
        dom.layerMenuButton.focus();
      } else if (dom.search.value) {
        dom.search.value = '';
        updateSearch();
        dom.search.blur();
      } else if (state.selectedId) {
        showOverviewDetail();
        updateNavigation();
      }
    });
  }

  function bindDetailResizer() {
    let drag = null;
    dom.detailResizer.addEventListener('pointerdown', (event) => {
      event.preventDefault();
      drag = {x: event.clientX, width: state.detailWidth};
      dom.detailResizer.classList.add('is-dragging');
      dom.detailResizer.setPointerCapture(event.pointerId);
    });
    dom.detailResizer.addEventListener('pointermove', (event) => {
      if (!drag) return;
      applyDetailWidth(drag.width + drag.x - event.clientX);
      resizeGraphPreservingViewport();
    });
    const endDrag = (event) => {
      if (!drag) return;
      drag = null;
      dom.detailResizer.classList.remove('is-dragging');
      if (dom.detailResizer.hasPointerCapture(event.pointerId)) {
        dom.detailResizer.releasePointerCapture(event.pointerId);
      }
    };
    dom.detailResizer.addEventListener('pointerup', endDrag);
    dom.detailResizer.addEventListener('pointercancel', endDrag);
    dom.detailResizer.addEventListener('dblclick', () => applyDetailWidth(384));
    dom.detailResizer.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home'].includes(event.key)) return;
      event.preventDefault();
      if (event.key === 'Home') applyDetailWidth(384);
      else applyDetailWidth(state.detailWidth + (event.key === 'ArrowLeft' ? 24 : -24));
      resizeGraphPreservingViewport();
    });
  }

  function applyDetailWidth(value) {
    const maximum = Math.max(320, Math.min(680, window.innerWidth - 520));
    state.detailWidth = Math.round(Math.max(320, Math.min(maximum, value)));
    document.documentElement.style.setProperty('--detail-width', `${state.detailWidth}px`);
    dom.detailResizer.setAttribute('aria-valuenow', String(state.detailWidth));
  }

  function applyDetailScale(value) {
    state.detailScale = Math.max(90, Math.min(150, value));
    document.documentElement.style.setProperty('--detail-scale', String(state.detailScale / 100));
    dom.detailTextSize.value = String(state.detailScale);
    dom.detailTextSizeValue.value = `${state.detailScale}%`;
    dom.detailTextSizeValue.textContent = `${state.detailScale}%`;
  }

  function resetUi() {
    applyDetailWidth(384);
    applyDetailScale(100);
    applyAppearanceScheme('faceted');
    hideNodeNameTooltip();
    resizeGraphPreservingViewport();
  }

  function resizeGraphPreservingViewport() {
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => cy.resize());
    });
  }

  function ensureGraphContentVisible() {
    cy.resize();
    const visibleNodes = cy.nodes().filter((node) => !node.hasClass('hidden'));
    if (!visibleNodes.length) return;
    const width = cy.width();
    const height = cy.height();
    const hasVisibleCenter = visibleNodes.some((node) => {
      const position = node.renderedPosition();
      return position.x >= 0 && position.x <= width && position.y >= 0 && position.y <= height;
    });
    if (!hasVisibleCenter) fitVisible();
  }

  function allReaderNodes() {
    return cy.nodes().filter((node) => node.data('kind') === 'reader-node');
  }

  function allThemeNodes() {
    return cy.nodes().filter((node) => node.data('kind') === 'theme');
  }

  function nodeEligible(nodeId) {
    const node = nodeById.get(nodeId);
    if (!node) return false;
    if (node.layer === 'research' && !state.includeResearch) return false;
    if (node.plane === 'learning' && !state.includeLearning) return false;
    if (node.plane === 'reader' && !state.includeReader) return false;
    return true;
  }

  function edgeEligible(edge) {
    if (!edge || !nodeEligible(edge.source) || !nodeEligible(edge.target)) return false;
    if (edge.weak && !state.includeWeak) return false;
    if (edge.layer === 'research' && !state.includeResearch) return false;
    return true;
  }

  function showOverview() {
    applyCanonicalPositions();
    refreshSurface({preserveViewport: false});
    fitVisible();
    showOverviewDetail();
  }

  function incidentEdges(nodeId, direction) {
    const edges = direction === 'upstream'
      ? incomingEdgesByNode.get(nodeId)
      : outgoingEdgesByNode.get(nodeId);
    return (edges || []).filter(edgeEligible);
  }

  function neighborFor(edge, nodeId) {
    if (edge.source === nodeId) return edge.target;
    if (edge.target === nodeId) return edge.source;
    return null;
  }

  function eligibleEdgeIds() {
    return new Set(packet.edges.filter(edgeEligible).map((edge) => edge.id));
  }

  function eligibleNodeIds() {
    return new Set(packet.nodes.filter((node) => nodeEligible(node.id)).map((node) => node.id));
  }

  function eligibleTargetIds() {
    return packet.target_order.filter(nodeEligible);
  }

  function currentVisibleIds() {
    return eligibleNodeIds();
  }

  function refreshSurface(options) {
    const preserveViewport = !options || options.preserveViewport !== false;
    const viewport = preserveViewport ? {zoom: cy.zoom(), pan: {...cy.pan()}} : null;
    const visibleIds = currentVisibleIds();
    setVisibility(visibleIds);
    applyNodeSizingClasses();
    cy.elements().unselect();
    const selected = cy.getElementById(state.selectedId || '');
    if (selected.length && !selected.hasClass('hidden')) selected.select();
    updateViewDescription();
    updateButtons();
    updateNavigation();
    renderNodeControls();
    updateSearch();
    updateEdgeDensity();
    if (viewport) {
      cy.zoom(viewport.zoom);
      cy.pan(viewport.pan);
    }
    scheduleNodeControlSync();
  }

  function directedClosureNodeIds(nodeId, direction) {
    if (!nodeEligible(nodeId)) return new Set();
    const result = new Set([nodeId]);
    const queue = [nodeId];
    for (let cursor = 0; cursor < queue.length; cursor += 1) {
      const current = queue[cursor];
      for (const edge of incidentEdges(current, direction)) {
        const neighborId = neighborFor(edge, current);
        if (!neighborId || result.has(neighborId)) continue;
        result.add(neighborId);
        queue.push(neighborId);
      }
    }
    return result;
  }

  function sameSet(left, right) {
    return left.size === right.size && [...left].every((value) => right.has(value));
  }

  function commitSizing(nextMinimizedNodeIds, label) {
    const next = new Set([...nextMinimizedNodeIds].filter((nodeId) => nodeById.has(nodeId)));
    if (sameSet(state.minimizedNodeIds, next)) return false;
    const delta = {
      added: [...next].filter((nodeId) => !state.minimizedNodeIds.has(nodeId)),
      removed: [...state.minimizedNodeIds].filter((nodeId) => !next.has(nodeId)),
      label
    };
    state.sizingUndoStack.push(delta);
    if (state.sizingUndoStack.length > SIZE_HISTORY_LIMIT) state.sizingUndoStack.shift();
    state.sizingRedoStack.length = 0;
    state.minimizedNodeIds = next;
    closeNodeContextMenu();
    refreshSurface({preserveViewport: true});
    return true;
  }

  function applySizingDelta(delta, reverse) {
    const next = new Set(state.minimizedNodeIds);
    const add = reverse ? delta.removed : delta.added;
    const remove = reverse ? delta.added : delta.removed;
    for (const nodeId of remove) next.delete(nodeId);
    for (const nodeId of add) next.add(nodeId);
    state.minimizedNodeIds = next;
    refreshSurface({preserveViewport: true});
  }

  function undoSizing() {
    const delta = state.sizingUndoStack.pop();
    if (!delta) return;
    state.sizingRedoStack.push(delta);
    applySizingDelta(delta, true);
  }

  function redoSizing() {
    const delta = state.sizingRedoStack.pop();
    if (!delta) return;
    state.sizingUndoStack.push(delta);
    applySizingDelta(delta, false);
  }

  function toggleNodeMinimized(nodeId) {
    if (!nodeById.has(nodeId) || !nodeEligible(nodeId)) return;
    const next = new Set(state.minimizedNodeIds);
    if (next.has(nodeId)) next.delete(nodeId);
    else next.add(nodeId);
    commitSizing(next, `toggle:${nodeId}`);
  }

  function maximizeAllCards() {
    const next = new Set(state.minimizedNodeIds);
    for (const nodeId of eligibleNodeIds()) next.delete(nodeId);
    commitSizing(next, 'all-cards');
  }

  function maximizeTargets() {
    const targets = new Set(eligibleTargetIds());
    const next = new Set(state.minimizedNodeIds);
    for (const nodeId of eligibleNodeIds()) {
      if (targets.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
    }
    commitSizing(next, 'all-targets');
  }

  function maximizeNodePath(nodeId) {
    if (!nodeEligible(nodeId)) return;
    const closure = new Set([
      ...directedClosureNodeIds(nodeId, 'upstream'),
      ...directedClosureNodeIds(nodeId, 'downstream')
    ]);
    const next = new Set(state.minimizedNodeIds);
    for (const eligibleId of eligibleNodeIds()) {
      if (closure.has(eligibleId)) next.delete(eligibleId);
      else next.add(eligibleId);
    }
    commitSizing(next, `complete-path:${nodeId}`);
    showNodeDetail(nodeId);
  }

  function maximizeThemePath(themeId) {
    const theme = themeById.get(themeId);
    if (!theme) return;
    const closure = new Set();
    for (const targetId of theme.target_ids.filter(nodeEligible)) {
      for (const nodeId of directedClosureNodeIds(targetId, 'upstream')) closure.add(nodeId);
      for (const nodeId of directedClosureNodeIds(targetId, 'downstream')) closure.add(nodeId);
    }
    if (!closure.size) return;
    const next = new Set(state.minimizedNodeIds);
    for (const eligibleId of eligibleNodeIds()) {
      if (closure.has(eligibleId)) next.delete(eligibleId);
      else next.add(eligibleId);
    }
    commitSizing(next, `theme-path:${themeId}`);
    showThemeDetail(themeId);
  }

  function maximizeDirection(nodeId, direction) {
    if (!nodeEligible(nodeId)) return;
    const next = new Set(state.minimizedNodeIds);
    for (const closureId of directedClosureNodeIds(nodeId, direction)) next.delete(closureId);
    commitSizing(next, `${direction}:${nodeId}`);
    showNodeDetail(nodeId);
  }

  function applyNodeSizingClasses() {
    const transitions = [];
    for (const nodeId of readerNodeIds) {
      const node = cy.getElementById(nodeId);
      if (!node.length) continue;
      const wasMinimized = node.hasClass('minimized');
      const minimized = state.minimizedNodeIds.has(nodeId);
      if (wasMinimized === minimized) continue;
      transitions.push({
        node,
        nodeId,
        minimized,
        oldAnchor: nodeSizeControlAnchor(node)
      });
    }
    cy.batch(() => {
      for (const nodeId of readerNodeIds) {
        const node = cy.getElementById(nodeId);
        const minimized = state.minimizedNodeIds.has(nodeId);
        if (minimized) node.addClass('minimized');
        else node.removeClass('minimized');
        node.data('minimized', minimized ? 'yes' : 'no');
      }
    });
    const zoom = cy.zoom();
    if (!Number.isFinite(zoom) || zoom <= 0) return;
    cy.batch(() => {
      for (const transition of transitions) {
        const newAnchor = nodeSizeControlAnchor(transition.node);
        const position = transition.node.position();
        const compensated = {
          x: position.x + (transition.oldAnchor.x - newAnchor.x) / zoom,
          y: position.y + (transition.oldAnchor.y - newAnchor.y) / zoom
        };
        transition.node.position(compensated);
        if (state.pinned.has(transition.nodeId)) {
          state.pinned.set(transition.nodeId, {...compensated});
        }
      }
    });
  }

  function refreshForLayerChange() {
    closeNodeContextMenu();
    hideNodeNameTooltip();
    refreshSurface({preserveViewport: true});
  }

  function resetCurrentLayout() {
    applyCanonicalPositions();
    refreshSurface({preserveViewport: true});
    fitVisible();
  }

  function updateViewDescription() {
    const eligible = eligibleNodeIds();
    const minimized = [...eligible].filter((nodeId) => state.minimizedNodeIds.has(nodeId)).length;
    const full = eligible.size - minimized;
    dom.cy.dataset.visibleNodeCount = String(eligible.size);
    dom.cy.dataset.visibleReaderEdgeCount = String(packet.edges.filter(edgeEligible).length);
    dom.cy.dataset.fullNodeCount = String(full);
    dom.cy.dataset.minimizedNodeCount = String(minimized);
    dom.viewDescription.textContent = bi(
      `完整 ${full} · 最小化 ${minimized} · 所有当前启用的关系保持可见`,
      `Full ${full} · Minimized ${minimized} · All enabled relations remain visible`
    );
  }

  function setVisibility(visibleIds) {
    cy.batch(() => {
      cy.elements().addClass('hidden');
      for (const nodeId of visibleIds) cy.getElementById(nodeId).removeClass('hidden');
      for (const themeId of groupedThemeIds) {
        const themeTargets = themeById.get(themeId).target_ids.filter((id) => visibleIds.has(id));
        if (!themeTargets.length) continue;
        cy.getElementById(`reader-theme:${themeId}`).removeClass('hidden');
        for (const targetId of themeTargets) {
          cy.getElementById(`reader-group:${themeId}:${targetId}`).removeClass('hidden');
        }
      }
      for (const edge of packet.edges) {
        if (!visibleIds.has(edge.source) || !visibleIds.has(edge.target)) continue;
        if (!edgeEligible(edge)) continue;
        cy.getElementById(edge.id).removeClass('hidden');
      }
    });
  }

  function cloneGroupOrder(groups) {
    return new Map([...groups].map(([rank, nodeIds]) => [rank, [...nodeIds]]));
  }

  function restoreGroupOrder(groups, savedOrder) {
    for (const [rank, nodeIds] of savedOrder) {
      groups.set(rank, [...nodeIds]);
    }
  }

  function layoutCrossingScore(groups, ranks, baselineIndex) {
    const position = new Map();
    for (const [rank, nodeIds] of groups) {
      nodeIds.forEach((nodeId, index) => position.set(nodeId, {x: rank, y: index}));
    }
    const edgeWeight = {prerequisite: 4, support: 2, repair: 1, conflict: 1};
    const segments = [];
    for (const edge of packet.edges) {
      const source = position.get(edge.source);
      const target = position.get(edge.target);
      if (!source || !target || source.x === target.x) continue;
      segments.push({
        sourceId: edge.source,
        targetId: edge.target,
        source,
        target,
        weight: edgeWeight[edge.category] || 1
      });
    }
    if (segments.length > CROSSING_REDUCTION_EDGE_LIMIT) return null;

    const orientation = (first, second, third) => (
      (second.x - first.x) * (third.y - first.y)
      - (second.y - first.y) * (third.x - first.x)
    );
    const properCrossing = (left, right) => {
      if (
        left.sourceId === right.sourceId
        || left.sourceId === right.targetId
        || left.targetId === right.sourceId
        || left.targetId === right.targetId
      ) return false;
      const first = orientation(left.source, left.target, right.source);
      const second = orientation(left.source, left.target, right.target);
      const third = orientation(right.source, right.target, left.source);
      const fourth = orientation(right.source, right.target, left.target);
      return (
        ((first > 0 && second < 0) || (first < 0 && second > 0))
        && ((third > 0 && fourth < 0) || (third < 0 && fourth > 0))
      );
    };

    let crossings = 0;
    let weightedPenalty = 0;
    for (let leftIndex = 0; leftIndex < segments.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < segments.length; rightIndex += 1) {
        const left = segments[leftIndex];
        const right = segments[rightIndex];
        if (!properCrossing(left, right)) continue;
        crossings += 1;
        weightedPenalty += left.weight * right.weight;
      }
    }
    let packetOrderDisplacement = 0;
    for (const [nodeId, coordinates] of position) {
      packetOrderDisplacement += Math.abs(coordinates.y - baselineIndex.get(nodeId));
    }
    return {crossings, weightedPenalty, packetOrderDisplacement};
  }

  function crossingScoreIsBetter(candidate, incumbent) {
    if (!candidate || !incumbent) return false;
    return (
      candidate.crossings < incumbent.crossings
      || (
        candidate.crossings === incumbent.crossings
        && candidate.weightedPenalty < incumbent.weightedPenalty
      )
      || (
        candidate.crossings === incumbent.crossings
        && candidate.weightedPenalty === incumbent.weightedPenalty
        && candidate.packetOrderDisplacement < incumbent.packetOrderDisplacement
      )
    );
  }

  function reduceEdgeCrossings(groups, ranks) {
    const orderedRanks = [...groups.keys()].sort((left, right) => left - right);
    const neighbors = new Map(readerNodeIds.map((nodeId) => [nodeId, []]));
    const edgeWeight = {prerequisite: 4, support: 2, repair: 1, conflict: 1};
    for (const edge of packet.edges) {
      if (!neighbors.has(edge.source) || !neighbors.has(edge.target)) continue;
      if (ranks.get(edge.source) === ranks.get(edge.target)) continue;
      const weight = edgeWeight[edge.category] || 1;
      neighbors.get(edge.source).push({nodeId: edge.target, weight});
      neighbors.get(edge.target).push({nodeId: edge.source, weight});
    }

    const sweep = (rankOrder, towardLowerRanks) => {
      const orderIndex = new Map();
      for (const [neighborRank, neighborIds] of groups) {
        neighborIds.forEach((nodeId, index) => {
          orderIndex.set(nodeId, {
            rank: neighborRank,
            normalized: (index + 0.5) / neighborIds.length
          });
        });
      }
      for (const rank of rankOrder) {
        const ids = groups.get(rank);
        if (!ids || ids.length < 2) continue;
        const previousIndex = new Map(ids.map((nodeId, index) => [nodeId, index]));
        const score = new Map();
        for (const nodeId of ids) {
          let weightedPosition = 0;
          let totalWeight = 0;
          for (const neighbor of neighbors.get(nodeId)) {
            const position = orderIndex.get(neighbor.nodeId);
            if (!position) continue;
            const usable = towardLowerRanks ? position.rank < rank : position.rank > rank;
            if (!usable) continue;
            weightedPosition += position.normalized * neighbor.weight;
            totalWeight += neighbor.weight;
          }
          score.set(
            nodeId,
            totalWeight
              ? weightedPosition / totalWeight
              : (previousIndex.get(nodeId) + 0.5) / ids.length
          );
        }
        ids.sort((left, right) => (
          score.get(left) - score.get(right)
          || previousIndex.get(left) - previousIndex.get(right)
          || nodeById.get(left).packetIndex - nodeById.get(right).packetIndex
        ));
        ids.forEach((nodeId, index) => {
          orderIndex.set(nodeId, {
            rank,
            normalized: (index + 0.5) / ids.length
          });
        });
      }
    };

    const baselineOrder = cloneGroupOrder(groups);
    const baselineIndex = new Map();
    for (const nodeIds of baselineOrder.values()) {
      nodeIds.forEach((nodeId, index) => baselineIndex.set(nodeId, index));
    }
    let bestOrder = cloneGroupOrder(groups);
    let bestScore = layoutCrossingScore(groups, ranks, baselineIndex);
    if (!bestScore) {
      return {evaluated: false, baselineCrossings: null, finalCrossings: null};
    }
    const considerCurrentOrder = () => {
      const candidateScore = layoutCrossingScore(groups, ranks, baselineIndex);
      if (!crossingScoreIsBetter(candidateScore, bestScore)) return;
      bestScore = candidateScore;
      bestOrder = cloneGroupOrder(groups);
    };

    for (let iteration = 0; iteration < CROSSING_REDUCTION_SWEEPS; iteration += 1) {
      sweep(orderedRanks.slice(1), true);
      considerCurrentOrder();
      sweep([...orderedRanks].reverse().slice(1), false);
      considerCurrentOrder();
    }
    restoreGroupOrder(groups, bestOrder);
    const baselineScore = layoutCrossingScore(baselineOrder, ranks, baselineIndex);
    return {
      evaluated: true,
      baselineCrossings: baselineScore.crossings,
      finalCrossings: bestScore.crossings
    };
  }

  function applyCanonicalPositions() {
    const nodeIds = packet.nodes.map((node) => node.id);
    cy.batch(() => {
      for (const nodeId of nodeIds) {
        const node = cy.getElementById(nodeId);
        node.removeClass('minimized');
        node.data('minimized', 'no');
      }
    });
    const ranks = new Map(nodeIds.map((id) => [id, 0]));
    const indegree = new Map(nodeIds.map((id) => [id, 0]));
    const outgoing = new Map(nodeIds.map((id) => [id, []]));
    for (const edge of packet.edges) {
      if (edge.category !== 'prerequisite') continue;
      outgoing.get(edge.source).push(edge.target);
      indegree.set(edge.target, indegree.get(edge.target) + 1);
    }
    const queue = [...nodeIds]
      .filter((id) => indegree.get(id) === 0)
      .sort((left, right) => nodeById.get(left).packetIndex - nodeById.get(right).packetIndex);
    for (let cursor = 0; cursor < queue.length; cursor += 1) {
      const current = queue[cursor];
      for (const target of outgoing.get(current)) {
        ranks.set(target, Math.max(ranks.get(target), ranks.get(current) + 1));
        indegree.set(target, indegree.get(target) - 1);
        if (indegree.get(target) === 0) queue.push(target);
      }
    }
    const groups = new Map();
    for (const nodeId of nodeIds) {
      const rank = ranks.get(nodeId) || 0;
      if (!groups.has(rank)) groups.set(rank, []);
      groups.get(rank).push(nodeId);
    }
    for (const ids of groups.values()) {
      ids.sort((left, right) => nodeById.get(left).packetIndex - nodeById.get(right).packetIndex);
    }
    const crossingDiagnostics = reduceEdgeCrossings(groups, ranks);
    dom.cy.dataset.layoutCrossingEvaluation = crossingDiagnostics.evaluated ? 'bounded' : 'skipped-large-graph';
    dom.cy.dataset.layoutBaselineCrossings = crossingDiagnostics.baselineCrossings === null
      ? 'not-evaluated'
      : String(crossingDiagnostics.baselineCrossings);
    dom.cy.dataset.layoutFinalCrossings = crossingDiagnostics.finalCrossings === null
      ? 'not-evaluated'
      : String(crossingDiagnostics.finalCrossings);
    for (const [rank, ids] of [...groups.entries()].sort((a, b) => a[0] - b[0])) {
      ids.forEach((nodeId, index) => setPosition(nodeId, {x: 285 + rank * CANONICAL_COLUMN_SPACING, y: 115 + index * 132}));
    }
    for (const themeId of groupedThemeIds) {
      const targetPositions = themeById.get(themeId).target_ids
        .map((targetId) => cy.getElementById(targetId))
        .filter((node) => node.length)
        .map((node) => node.position());
      if (!targetPositions.length) continue;
      const minimumX = Math.min(...targetPositions.map((position) => position.x));
      const averageY = targetPositions.reduce((sum, position) => sum + position.y, 0) / targetPositions.length;
      setPosition(`reader-theme:${themeId}`, {x: minimumX - 280, y: averageY});
    }
  }

  function setPosition(nodeId, position) {
    const node = cy.getElementById(nodeId);
    if (!node.length) return;
    const pinned = state.pinned.get(nodeId);
    node.position(pinned || position);
  }

  function fitVisible() {
    const visible = cy.elements().filter((element) => !element.hasClass('hidden'));
    if (!visible.length) return;
    window.requestAnimationFrame(() => {
      cy.fit(visible, 52);
      if (cy.zoom() > 1.12) {
        cy.zoom(1.12);
        cy.center(visible);
      }
    });
  }

  function updateButtons() {
    const eligible = eligibleNodeIds();
    const targets = new Set(eligibleTargetIds());
    const allCardsActive = [...eligible].every((nodeId) => !state.minimizedNodeIds.has(nodeId));
    const allTargetsActive = [...eligible].every((nodeId) => (
      targets.has(nodeId) ? !state.minimizedNodeIds.has(nodeId) : state.minimizedNodeIds.has(nodeId)
    ));
    dom.overview.disabled = false;
    dom.allCards.disabled = false;
    dom.overview.setAttribute('aria-pressed', allTargetsActive ? 'true' : 'false');
    dom.allCards.setAttribute('aria-pressed', allCardsActive ? 'true' : 'false');
    dom.headerOverview.setAttribute('aria-pressed', allTargetsActive ? 'true' : 'false');
    dom.undoSizing.disabled = state.sizingUndoStack.length === 0;
    dom.redoSizing.disabled = state.sizingRedoStack.length === 0;
    dom.undoSizing.title = state.sizingUndoStack.length
      ? bi(`撤销：${state.sizingUndoStack.at(-1).label}`, `Undo: ${state.sizingUndoStack.at(-1).label}`)
      : bi('没有可撤销的尺寸操作', 'No sizing action to undo');
    dom.redoSizing.title = state.sizingRedoStack.length
      ? bi(`重做：${state.sizingRedoStack.at(-1).label}`, `Redo: ${state.sizingRedoStack.at(-1).label}`)
      : bi('没有可重做的尺寸操作', 'No sizing action to redo');
    dom.cy.dataset.sizingUndoDepth = String(state.sizingUndoStack.length);
    dom.cy.dataset.sizingRedoDepth = String(state.sizingRedoStack.length);
  }

  function selectedTargetId() {
    const selected = nodeById.get(state.selectedId);
    if (selected && selected.reader_role === 'target' && nodeEligible(selected.id)) return selected.id;
    return null;
  }

  function navigateTarget(delta) {
    const orderedTargets = eligibleTargetIds();
    if (!orderedTargets.length) return;
    const currentId = selectedTargetId();
    const currentIndex = currentId ? orderedTargets.indexOf(currentId) : (delta > 0 ? -1 : 0);
    const nextIndex = (currentIndex + delta + orderedTargets.length) % orderedTargets.length;
    const nextId = orderedTargets[nextIndex];
    const element = cy.getElementById(nextId);
    showNodeDetail(nextId);
    updateNavigation();
    if (element.length) cy.animate({center: {eles: element}, duration: 220});
  }

  function updateNavigation() {
    const targetId = selectedTargetId();
    const total = packet.target_order.length;
    const available = eligibleTargetIds();
    dom.previousTarget.disabled = available.length < 2;
    dom.nextTarget.disabled = available.length < 2;
    if (!targetId) {
      dom.targetPosition.textContent = available.length === total
        ? bi(`${total} 个目标`, `${total} target${total === 1 ? '' : 's'}`)
        : bi(`${available.length}/${total} 个目标可用`, `${available.length}/${total} targets available`);
    } else {
      const index = targetOrderIndex.get(targetId) + 1;
      dom.targetPosition.textContent = bi(`已选目标 ${index}/${total}`, `Selected target ${index}/${total}`);
    }
  }

  function svgIcon(iconId) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('aria-hidden', 'true');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', `#reader-icon-${iconId}`);
    svg.append(use);
    return svg;
  }

  function nodeSizeControlSize(node) {
    const compact = COMPACT_NODE_SIZES[node.data('role')] || COMPACT_NODE_SIZES.explanation;
    return Math.max(
      NODE_SIZE_CONTROL_MIN_PX,
      Math.min(
        NODE_SIZE_CONTROL_MAX_PX,
        compact.height * cy.zoom() * NODE_SIZE_CONTROL_CARD_HEIGHT_RATIO
      )
    );
  }

  function nodeSizeControlAnchor(node) {
    const bounds = renderedNodeBox(node);
    if (!bounds) return node.renderedPosition();
    return {
      x: bounds.x1 + (bounds.x2 - bounds.x1) * NODE_SIZE_CONTROL_X_RATIO,
      y: bounds.y1 + (bounds.y2 - bounds.y1) * NODE_SIZE_CONTROL_Y_RATIO
    };
  }

  function bindNodeSizeToggle(button, nodeId) {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      toggleNodeMinimized(nodeId);
      window.requestAnimationFrame(() => {
        const replacement = [...dom.nodeControlLayer.querySelectorAll('.node-size-toggle')]
          .find((candidate) => candidate.dataset.nodeId === nodeId);
        if (replacement && !replacement.hidden) replacement.focus({preventScroll: true});
      });
    });
    button.addEventListener('dragstart', (event) => event.preventDefault());
  }

  function renderNodeControls() {
    dom.nodeControlLayer.replaceChildren();
    dom.cy.dataset.selectedId = state.selectedId || '';
    const visibleNodes = packet.nodes.filter((node) => {
      const element = cy.getElementById(node.id);
      return element.length && !element.hasClass('hidden');
    });
    for (const node of visibleNodes) {
      const minimized = state.minimizedNodeIds.has(node.id);
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'node-size-toggle';
      button.dataset.nodeId = node.id;
      button.dataset.minimized = minimized ? 'yes' : 'no';
      button.dataset.plane = node.plane;
      button.dataset.selected = node.id === state.selectedId ? 'yes' : 'no';
      const action = minimized ? bi('最大化卡片', 'Maximize card') : bi('最小化卡片', 'Minimize card');
      button.setAttribute('aria-label', `${action}: ${node.title}`);
      button.setAttribute('aria-pressed', minimized ? 'true' : 'false');
      if (!minimized) button.title = `${action}: ${node.title}`;
      button.append(svgIcon(minimized ? 'expand' : 'collapse'));
      const enterControl = () => {
        state.hoveredControlNodeId = node.id;
        scheduleNodeHoverSync();
      };
      const leaveControl = () => {
        if (state.hoveredControlNodeId === node.id) {
          state.hoveredControlNodeId = null;
        }
        scheduleNodeHoverSync();
      };
      button.addEventListener('mouseenter', enterControl);
      button.addEventListener('mouseleave', leaveControl);
      button.addEventListener('focus', () => showNodeNameTooltip(node.id));
      button.addEventListener('blur', () => {
        if (!state.hoveredCanvasNodeId && !state.hoveredControlNodeId) {
          hideNodeNameTooltip();
        }
      });
      bindNodeSizeToggle(button, node.id);
      button.addEventListener('contextmenu', (event) => {
        event.preventDefault();
        event.stopPropagation();
        openNodeContextMenu(
          node.id,
          cy.getElementById(node.id).renderedPosition(),
          {returnFocus: button}
        );
      });
      dom.nodeControlLayer.append(button);
    }
    scheduleNodeControlSync();
  }

  function scheduleNodeControlSync() {
    if (nodeControlFrame) return;
    nodeControlFrame = window.requestAnimationFrame(() => {
      nodeControlFrame = 0;
      syncNodeControls();
    });
  }

  function renderedNodeBox(node) {
    const center = node.renderedPosition();
    const width = node.renderedOuterWidth();
    const height = node.renderedOuterHeight();
    if (![center.x, center.y, width, height].every(Number.isFinite)) return null;
    return {
      x1: center.x - width / 2,
      x2: center.x + width / 2,
      y1: center.y - height / 2,
      y2: center.y + height / 2
    };
  }

  function syncNodeControls() {
    const stageWidth = dom.canvasStage.clientWidth;
    const stageHeight = dom.canvasStage.clientHeight;
    const intersectsStage = (bounds) => (
      bounds.x2 >= 0 && bounds.x1 <= stageWidth
      && bounds.y2 >= 0 && bounds.y1 <= stageHeight
    );
    const controlIntersectsStage = (x, y, width, height) => (
      x + width / 2 >= 0 && x - width / 2 <= stageWidth
      && y + height / 2 >= 0 && y - height / 2 <= stageHeight
    );
    for (const button of dom.nodeControlLayer.querySelectorAll('.node-size-toggle')) {
      const node = cy.getElementById(button.dataset.nodeId);
      const bounds = node.length ? renderedNodeBox(node) : null;
      if (!bounds || node.hasClass('hidden') || !intersectsStage(bounds)) {
        button.hidden = true;
        continue;
      }
      const controlSize = nodeSizeControlSize(node);
      button.style.width = `${controlSize}px`;
      button.style.height = `${controlSize}px`;
      const anchor = nodeSizeControlAnchor(node);
      const x = anchor.x;
      const y = anchor.y;
      const hasInternalRoom = (
        x - controlSize / 2 >= bounds.x1 + 2
        && x + controlSize / 2 <= bounds.x2 - 2
        && y - controlSize / 2 >= bounds.y1 + 2
        && y + controlSize / 2 <= bounds.y2 - 2
      );
      const modelPosition = node.position();
      button.dataset.modelX = String(modelPosition.x);
      button.dataset.modelY = String(modelPosition.y);
      button.dataset.renderedCenterX = String((bounds.x1 + bounds.x2) / 2);
      button.dataset.renderedCenterY = String((bounds.y1 + bounds.y2) / 2);
      button.dataset.nodeWidth = String(bounds.x2 - bounds.x1);
      button.dataset.nodeHeight = String(bounds.y2 - bounds.y1);
      button.hidden = !hasInternalRoom || !controlIntersectsStage(x, y, controlSize, controlSize);
      button.style.left = `${x}px`;
      button.style.top = `${y}px`;
    }
    syncSelectedNodeHalo();
    syncNodeNameTooltip();
  }

  function syncSelectedNodeHalo() {
    const nodeData = nodeById.get(state.selectedId);
    const node = cy.getElementById(state.selectedId || '');
    if (!nodeData || !node.length || node.hasClass('hidden')) {
      dom.selectedNodeHalo.hidden = true;
      return;
    }
    const bounds = renderedNodeBox(node);
    if (!bounds) {
      dom.selectedNodeHalo.hidden = true;
      return;
    }
    const minimized = state.minimizedNodeIds.has(nodeData.id);
    const padding = minimized ? 4 : 6;
    dom.selectedNodeHalo.dataset.appearance = state.appearanceScheme;
    dom.selectedNodeHalo.dataset.role = nodeData.reader_role;
    dom.selectedNodeHalo.dataset.minimized = minimized ? 'yes' : 'no';
    dom.selectedNodeHalo.style.left = `${(bounds.x1 + bounds.x2) / 2}px`;
    dom.selectedNodeHalo.style.top = `${(bounds.y1 + bounds.y2) / 2}px`;
    dom.selectedNodeHalo.style.width = `${bounds.x2 - bounds.x1 + padding * 2}px`;
    dom.selectedNodeHalo.style.height = `${bounds.y2 - bounds.y1 + padding * 2}px`;
    dom.selectedNodeHalo.hidden = false;
  }

  function showNodeNameTooltip(nodeId) {
    if (!state.minimizedNodeIds.has(nodeId)) return;
    const node = nodeById.get(nodeId);
    if (!node) return;
    state.tooltipNodeId = nodeId;
    dom.nodeNameTooltip.textContent = node.title;
    dom.nodeNameTooltip.hidden = false;
    syncNodeNameTooltip();
  }

  function hideNodeNameTooltip() {
    state.tooltipNodeId = null;
    dom.nodeNameTooltip.hidden = true;
  }

  function syncNodeNameTooltip() {
    const nodeId = state.tooltipNodeId;
    const node = cy.getElementById(nodeId || '');
    if (!nodeId || !node.length || node.hasClass('hidden') || !state.minimizedNodeIds.has(nodeId)) {
      state.tooltipNodeId = null;
      dom.nodeNameTooltip.hidden = true;
      return;
    }
    const bounds = renderedNodeBox(node);
    if (!bounds) return;
    const tooltipWidth = dom.nodeNameTooltip.offsetWidth;
    const tooltipHeight = dom.nodeNameTooltip.offsetHeight;
    const x = Math.max(8, Math.min(dom.canvasStage.clientWidth - tooltipWidth - 8, (bounds.x1 + bounds.x2 - tooltipWidth) / 2));
    const y = Math.max(8, Math.min(dom.canvasStage.clientHeight - tooltipHeight - 8, bounds.y1 - tooltipHeight - 9));
    dom.nodeNameTooltip.style.left = `${x}px`;
    dom.nodeNameTooltip.style.top = `${y}px`;
    dom.nodeNameTooltip.hidden = false;
  }

  function scheduleNodeHoverSync() {
    if (nodeHoverFrame) return;
    nodeHoverFrame = window.requestAnimationFrame(() => {
      nodeHoverFrame = 0;
      const nextHoveredId = (
        state.hoveredControlNodeId
        || state.hoveredCanvasNodeId
        || null
      );
      if (state.hoveredNodeId === nextHoveredId) return;
      state.hoveredNodeId = nextHoveredId;
      updateEdgeDensity();
      if (nextHoveredId) showNodeNameTooltip(nextHoveredId);
      else hideNodeNameTooltip();
    });
  }

  function updateEdgeDensity() {
    const emphasizedId = state.hoveredNodeId || (nodeById.has(state.selectedId) ? state.selectedId : null);
    cy.batch(() => {
      cy.edges().removeClass('compact-edge edge-dim edge-related');
      cy.edges().forEach((edge) => {
        if (edge.hasClass('hidden')) return;
        const sourceId = edge.source().id();
        const targetId = edge.target().id();
        if (state.minimizedNodeIds.has(sourceId) && state.minimizedNodeIds.has(targetId)) {
          edge.addClass('compact-edge');
        }
        if (emphasizedId) {
          if (sourceId === emphasizedId || targetId === emphasizedId) edge.addClass('edge-related');
          else edge.addClass('edge-dim');
        } else if (edge.selected()) {
          edge.addClass('edge-related');
        }
      });
    });
  }

  function bindTrackpadNavigation() {
    const graph = cy.container();
    const captureSurface = dom.canvasStage;
    let pendingX = 0;
    let pendingY = 0;
    let frame = 0;
    captureSurface.addEventListener('wheel', (event) => {
      if (!graph.contains(event.target)) return;
      if (event.ctrlKey) return;
      event.preventDefault();
      event.stopPropagation();
      closeNodeContextMenu();
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? graph.clientHeight : 1;
      pendingX += event.deltaX * unit;
      pendingY += event.deltaY * unit;
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        cy.panBy({x: -pendingX, y: -pendingY});
        pendingX = 0;
        pendingY = 0;
        frame = 0;
      });
    }, {capture: true, passive: false});
  }

  function openNodeContextMenu(nodeId, renderedPosition, options) {
    const node = nodeById.get(nodeId);
    if (!node) return;
    closeNodeContextMenu();
    state.contextNodeId = nodeId;
    state.contextReturnFocus = options && options.returnFocus
      ? options.returnFocus
      : dom.cy;
    showNodeDetail(nodeId);
    cy.getElementById(nodeId).addClass('context-node');
    dom.nodeContextMenuTitle.textContent = node.title;
    dom.nodeContextMenu.hidden = false;
    updateContextMenuCommands();
    const x = renderedPosition && Number.isFinite(renderedPosition.x) ? renderedPosition.x + 18 : 18;
    const y = renderedPosition && Number.isFinite(renderedPosition.y) ? renderedPosition.y + 18 : 18;
    const maximumX = Math.max(8, dom.canvasStage.clientWidth - dom.nodeContextMenu.offsetWidth - 8);
    const maximumY = Math.max(8, dom.canvasStage.clientHeight - dom.nodeContextMenu.offsetHeight - 8);
    dom.nodeContextMenu.style.left = `${Math.max(8, Math.min(maximumX, x))}px`;
    dom.nodeContextMenu.style.top = `${Math.max(8, Math.min(maximumY, y))}px`;
    if (!options || options.focusMenu !== false) {
      const first = dom.contextCommands.find((button) => !button.disabled);
      if (first) window.requestAnimationFrame(() => first.focus());
    }
  }

  function closeNodeContextMenu(options) {
    if (state.contextNodeId) cy.getElementById(state.contextNodeId).removeClass('context-node');
    state.contextNodeId = null;
    dom.nodeContextMenu.hidden = true;
    if (options && options.restoreFocus) {
      const returnFocus = state.contextReturnFocus;
      if (returnFocus && returnFocus.isConnected && typeof returnFocus.focus === 'function') returnFocus.focus();
      else dom.cy.focus();
    }
    state.contextReturnFocus = null;
  }

  function updateContextMenuCommands() {
    const nodeId = state.contextNodeId;
    if (!nodeById.has(nodeId)) return;
    const incoming = incidentEdges(nodeId, 'upstream');
    const outgoing = incidentEdges(nodeId, 'downstream');
    for (const button of dom.contextCommands) {
      const command = button.dataset.contextCommand;
      if (command === 'maximize-upstream') button.disabled = incoming.length === 0;
      else if (command === 'maximize-downstream') button.disabled = outgoing.length === 0;
    }
  }

  function runContextCommand(command) {
    const nodeId = state.contextNodeId;
    if (!nodeById.has(nodeId)) return;
    closeNodeContextMenu();
    if (command === 'maximize-upstream') maximizeDirection(nodeId, 'upstream');
    else if (command === 'maximize-downstream') maximizeDirection(nodeId, 'downstream');
  }

  function handleContextMenuKeydown(event) {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeNodeContextMenu({restoreFocus: true});
      return;
    }
    if (event.key === 'Tab') {
      closeNodeContextMenu();
      return;
    }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const items = dom.contextCommands.filter((button) => !button.disabled);
    if (!items.length) return;
    const current = items.indexOf(document.activeElement);
    const next = event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? items.length - 1
        : (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
    items[next].focus();
  }

  function closeLayerPopover() {
    dom.layerPopover.hidden = true;
    dom.layerMenuButton.setAttribute('aria-expanded', 'false');
  }

  function showOverviewDetail() {
    state.selectedId = null;
    cy.elements().unselect();
    allReaderNodes().removeClass('theme-member');
    dom.detail.scrollTop = 0;
    const eligible = eligibleNodeIds();
    const minimizedCount = [...eligible].filter((nodeId) => state.minimizedNodeIds.has(nodeId)).length;
    const fullCount = eligible.size - minimizedCount;
    dom.detailTitle.textContent = bi('知识图谱', 'Knowledge map');
    replaceBadges([
      bi(`${fullCount} 张完整卡片`, `${fullCount} full cards`),
      bi(`${minimizedCount} 张最小化卡片`, `${minimizedCount} minimized cards`),
      bi('关系始终保留', 'Relations always retained')
    ]);
    dom.detailReadable.replaceChildren();
    const section = document.createElement('section');
    const heading = document.createElement('h3');
    heading.textContent = bi('如何开始', 'How to begin');
    const introduction = document.createElement('p');
    introduction.textContent = bi(
      '所有已启用的节点和关系都保留在同一画布上。单击阅读；卡片内的减号或加号切换该卡片尺寸；双击任意节点会最大化它的完整上下游链，并最小化无关节点。',
      'Every eligible node and relation remains on one canvas. Select to read, use the minus or plus inside a card to change only its size, or double-click any node to maximize its complete upstream and downstream chain while minimizing unrelated nodes.'
    );
    section.append(heading, introduction);
    dom.detailReadable.append(section);
    const orderHeading = document.createElement('section');
    const orderTitle = document.createElement('h3');
    orderTitle.textContent = bi('目标阅读顺序', 'Target reading order');
    orderHeading.append(orderTitle);
    for (const themeId of packet.theme_order) {
      const theme = themeById.get(themeId);
      const themeTargetIds = theme.target_ids.filter(nodeEligible);
      if (!themeTargetIds.length) continue;
      const group = document.createElement('section');
      group.className = 'reader-order-group';
      const groupTitle = document.createElement('p');
      groupTitle.className = 'reader-order-group-title';
      groupTitle.textContent = theme.target_ids.length > 1
        ? `${bi('主题', 'Topic')}: ${theme.label}${theme.description ? ` — ${theme.description}` : ''}`
        : `${bi('主题标签', 'Topic label')}: ${theme.label}`;
      const list = document.createElement('ol');
      list.className = 'reader-order-list';
      for (const targetId of themeTargetIds) {
        const item = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'reader-order-item';
        const number = document.createElement('span');
        number.className = 'reader-order-number';
        number.textContent = String(targetOrderIndex.get(targetId) + 1).padStart(2, '0');
        const title = document.createElement('span');
        title.className = 'reader-order-title';
        title.textContent = nodeById.get(targetId).title;
        const hint = document.createElement('span');
        hint.className = 'reader-order-hint';
        hint.textContent = bi('选择', 'Select');
        button.append(number, title, hint);
        button.addEventListener('click', () => {
          showNodeDetail(targetId);
          updateNavigation();
          const targetElement = cy.getElementById(targetId);
          if (targetElement.length) cy.animate({center: {eles: targetElement}, duration: 220});
        });
        item.append(button);
        list.append(item);
      }
      group.append(groupTitle, list);
      orderHeading.append(group);
    }
    dom.detailReadable.append(orderHeading);
    dom.detailFormal.replaceChildren();
    dom.formalDetails.open = false;
    updateEdgeDensity();
    renderNodeControls();
  }

  function showThemeDetail(themeId) {
    const theme = themeById.get(themeId);
    state.selectedId = `reader-theme:${themeId}`;
    dom.detail.scrollTop = 0;
    dom.detailTitle.textContent = theme.label;
    replaceBadges([
      bi('阅读分组', 'Reader grouping'),
      bi(`${theme.target_ids.length} 个目标`, `${theme.target_ids.length} targets`),
      bi('仅用于展示', 'Presentation only')
    ]);
    allReaderNodes().removeClass('theme-member');
    for (const targetId of theme.target_ids) cy.getElementById(targetId).addClass('theme-member');
    dom.detailReadable.replaceChildren();
    appendSection(
      dom.detailReadable,
      bi('作用', 'Purpose'),
      theme.description || bi('这是导出器生成的阅读分组，不是 Chalxius 的新事实或关系。', 'This is a reader grouping created by the exporter, not a new Chalxius fact or relation.')
    );
    appendSection(
      dom.detailReadable,
      bi('边界', 'Boundary'),
      bi('虚线只表示展示分组；来源图谱仍是唯一权威。', 'Dashed links only show presentation grouping; the source graph remains authoritative.')
    );
    const section = document.createElement('section');
    const heading = document.createElement('h3');
    heading.textContent = bi('目标', 'Targets');
    const list = document.createElement('ol');
    for (const targetId of theme.target_ids) {
      const li = document.createElement('li');
      li.textContent = nodeById.get(targetId).title;
      list.append(li);
    }
    section.append(heading, list);
    dom.detailReadable.append(section);
    dom.detailFormal.replaceChildren();
    dom.formalDetails.open = false;
    updateNavigation();
    updateEdgeDensity();
    renderNodeControls();
  }

  function showNodeDetail(nodeId) {
    const node = nodeById.get(nodeId);
    if (!node) return;
    state.selectedId = nodeId;
    allReaderNodes().removeClass('theme-member');
    dom.detail.scrollTop = 0;
    cy.elements().unselect();
    cy.getElementById(nodeId).select();
    dom.detailTitle.textContent = node.title;
    const topic = themeById.get(node.theme_id);
    replaceBadges([
      roleLabel(node.reader_role),
      planeLabel(node.plane),
      visualStatusLabel(node.visual_status),
      node.layer === 'research' ? bi('研究过程', 'Research process') : bi('知识层', 'Knowledge'),
      topic ? `${bi('主题', 'Topic')}: ${topic.label}` : ''
    ]);
    dom.detailReadable.replaceChildren();
    appendSection(dom.detailReadable, bi('一句话概括', 'In one sentence'), node.summary);
    appendSection(dom.detailReadable, bi('直觉', 'Intuition'), node.intuition);
    appendSection(dom.detailReadable, bi('为何重要', 'Why it matters'), node.importance);
    appendPrerequisiteSection(node);
    appendSection(dom.detailReadable, bi('推理路线', 'Reasoning route'), node.reasoning);
    renderFormalNode(node);
    dom.formalDetails.open = false;
    typeset([dom.detailReadable, dom.detailFormal]);
    updateNavigation();
    updateEdgeDensity();
    renderNodeControls();
  }

  function appendPrerequisiteSection(node) {
    const section = document.createElement('section');
    const heading = document.createElement('h3');
    heading.textContent = bi('直接前置知识', 'Direct prerequisites');
    section.append(heading);
    if (!node.prerequisites.length) {
      const p = document.createElement('p');
      p.textContent = bi('本阅读包中不需要更早的节点。', 'No earlier node is required in this packet.');
      section.append(p);
    } else {
      const list = document.createElement('ul');
      for (const prerequisiteId of node.prerequisites) {
        const li = document.createElement('li');
        const prerequisite = nodeById.get(prerequisiteId);
        li.textContent = prerequisite ? prerequisite.title : prerequisiteId;
        list.append(li);
      }
      section.append(list);
    }
    dom.detailReadable.append(section);
  }

  function renderFormalNode(node) {
    const formal = node.formal;
    const provenance = node.provenance;
    dom.detailFormal.replaceChildren();
    if (formal.hypotheses.length) appendListBlock(dom.detailFormal, bi('假设', 'Hypotheses'), formal.hypotheses);
    appendFormalBlock(dom.detailFormal, bi('形式化陈述', 'Formal statement'), formal.statement);
    appendFormalBlock(dom.detailFormal, bi('证明或推理记录', 'Proof / reasoning record'), formal.proof);
    if (formal.relations.length) appendListBlock(dom.detailFormal, bi('精确关系', 'Exact relations'), formal.relations);

    const provenanceBlock = document.createElement('section');
    provenanceBlock.className = 'formal-block';
    const provenanceHeading = document.createElement('h3');
    provenanceHeading.textContent = bi('溯源', 'Provenance');
    provenanceBlock.append(provenanceHeading);
    provenanceBlock.append(provenanceTable([
      [bi('来源平面', 'Source plane'), planeLabel(provenance.source_plane)],
      [bi('来源状态', 'Source status'), provenance.source_status],
      [bi('真值效应', 'Truth effect'), truthLabel(provenance.truth_status)],
      [bi('快照', 'Snapshot'), provenance.snapshot_id],
      [bi('定位', 'Locator'), provenance.locator],
      [bi('替代', 'Replaces'), provenance.replaces.length ? provenance.replaces.join(', ') : bi('无记录', 'None recorded')]
    ]));

    const technical = document.createElement('details');
    technical.className = 'exact-source';
    const technicalSummary = document.createElement('summary');
    technicalSummary.textContent = bi('技术来源标识', 'Technical source identity');
    technical.append(technicalSummary, provenanceTable([
      [bi('对象 ID', 'Object ID'), provenance.object_id],
      ['Object SHA-256', provenance.object_sha256],
      ['Exact-text SHA-256', provenance.original_text_sha256]
    ]));
    const technicalCopy = document.createElement('button');
    technicalCopy.type = 'button';
    technicalCopy.className = 'quiet-button';
    technicalCopy.dataset.copyIdleZh = '复制溯源';
    technicalCopy.dataset.copyIdleEn = 'Copy provenance';
    technicalCopy.textContent = bi('复制溯源', 'Copy provenance');
    technicalCopy.addEventListener('click', () => copyText(JSON.stringify(provenance, null, 2), technicalCopy));
    technical.append(technicalCopy);
    provenanceBlock.append(technical);

    const exact = document.createElement('details');
    exact.className = 'exact-source';
    const exactSummary = document.createElement('summary');
    exactSummary.textContent = bi('精确原文', 'Exact original text');
    const pre = document.createElement('pre');
    pre.textContent = formal.original_text;
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'quiet-button';
    copy.dataset.copyIdleZh = '复制精确原文';
    copy.dataset.copyIdleEn = 'Copy exact text';
    copy.textContent = bi('复制精确原文', 'Copy exact text');
    copy.addEventListener('click', () => copyText(formal.original_text, copy));
    exact.append(exactSummary, pre, copy);
    provenanceBlock.append(exact);
    dom.detailFormal.append(provenanceBlock);
  }

  function showEdgeDetail(edgeId) {
    const edge = edgeById.get(edgeId);
    if (!edge) return;
    state.selectedId = edgeId;
    dom.detail.scrollTop = 0;
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    dom.detailTitle.textContent = edge.relation;
    replaceBadges([relationLabel(edge.category), edge.weak ? bi('上下文连接', 'Contextual link') : bi('主要连接', 'Primary link')]);
    dom.detailReadable.replaceChildren();
    appendSection(dom.detailReadable, bi('可读方向', 'Readable direction'), `${source.title} → ${target.title}`);
    appendSection(dom.detailReadable, bi('关系', 'Relation'), edge.relation);
    dom.detailFormal.replaceChildren();
    appendFormalBlock(dom.detailFormal, bi('精确关系类型', 'Exact relation type'), edge.exact_type);
    const provenanceBlock = document.createElement('section');
    provenanceBlock.className = 'formal-block';
    const heading = document.createElement('h3');
    heading.textContent = bi('溯源', 'Provenance');
    provenanceBlock.append(heading, provenanceTable([
      [bi('来源平面', 'Source plane'), planeLabel(edge.provenance.source_plane)],
      [bi('来源状态', 'Source status'), edge.provenance.source_status],
      [bi('真值效应', 'Truth effect'), truthLabel(edge.provenance.truth_status)],
      [bi('对象 ID', 'Object ID'), edge.provenance.object_id],
      [bi('快照', 'Snapshot'), edge.provenance.snapshot_id],
      [bi('定位', 'Locator'), edge.provenance.locator],
      ['Object SHA-256', edge.provenance.object_sha256]
    ]));
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'quiet-button';
    copy.dataset.copyIdleZh = '复制边溯源';
    copy.dataset.copyIdleEn = 'Copy edge provenance';
    copy.textContent = bi('复制边溯源', 'Copy edge provenance');
    copy.addEventListener('click', () => copyText(JSON.stringify(edge.provenance, null, 2), copy));
    provenanceBlock.append(copy);
    dom.detailFormal.append(provenanceBlock);
    dom.formalDetails.open = false;
    typeset([dom.detailReadable, dom.detailFormal]);
    updateNavigation();
    updateEdgeDensity();
    renderNodeControls();
  }

  function appendSection(parent, headingText, text) {
    if (!text) return;
    const section = document.createElement('section');
    const heading = document.createElement('h3');
    heading.textContent = headingText;
    section.append(heading);
    appendRichText(section, text);
    parent.append(section);
  }

  function appendFormalBlock(parent, headingText, text) {
    if (!text) return;
    const section = document.createElement('section');
    section.className = 'formal-block';
    const heading = document.createElement('h3');
    heading.textContent = headingText;
    section.append(heading);
    appendRichText(section, text);
    parent.append(section);
  }

  function appendListBlock(parent, headingText, items) {
    const section = document.createElement('section');
    section.className = 'formal-block';
    const heading = document.createElement('h3');
    heading.textContent = headingText;
    const list = document.createElement('ul');
    for (const item of items) {
      const li = document.createElement('li');
      appendInlineText(li, item);
      list.append(li);
    }
    section.append(heading, list);
    parent.append(section);
  }

  function appendRichText(parent, text) {
    const lines = text.split(/\r?\n/);
    let index = 0;
    while (index < lines.length) {
      if (!lines[index].trim()) { index += 1; continue; }
      const bullet = lines[index].match(/^\s*[-*]\s+(.+)$/);
      const numbered = lines[index].match(/^\s*\d+[.)]\s+(.+)$/);
      if (bullet || numbered) {
        const list = document.createElement(numbered ? 'ol' : 'ul');
        while (index < lines.length) {
          const match = lines[index].match(numbered ? /^\s*\d+[.)]\s+(.+)$/ : /^\s*[-*]\s+(.+)$/);
          if (!match) break;
          const li = document.createElement('li');
          appendInlineText(li, match[1]);
          list.append(li);
          index += 1;
        }
        parent.append(list);
        continue;
      }
      const paragraphLines = [];
      while (index < lines.length && lines[index].trim()) {
        if (/^\s*[-*]\s+/.test(lines[index]) || /^\s*\d+[.)]\s+/.test(lines[index])) break;
        paragraphLines.push(lines[index].trim());
        index += 1;
      }
      const p = document.createElement('p');
      appendInlineText(p, paragraphLines.join(' '));
      parent.append(p);
    }
  }

  function appendInlineText(parent, text) {
    const parts = text.split(/(`[^`]*`)/g);
    for (const part of parts) {
      if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
        const code = document.createElement('code');
        code.textContent = part.slice(1, -1);
        parent.append(code);
      } else {
        parent.append(document.createTextNode(part));
      }
    }
  }

  function provenanceTable(rows) {
    const table = document.createElement('table');
    table.className = 'provenance-table';
    const tbody = document.createElement('tbody');
    for (const [label, value] of rows) {
      const row = document.createElement('tr');
      const th = document.createElement('th');
      const td = document.createElement('td');
      th.scope = 'row';
      th.textContent = label;
      td.textContent = value;
      row.append(th, td);
      tbody.append(row);
    }
    table.append(tbody);
    return table;
  }

  function replaceBadges(labels) {
    dom.detailBadges.replaceChildren();
    for (const label of labels) {
      if (!label) continue;
      const span = document.createElement('span');
      span.className = 'badge';
      span.textContent = label;
      dom.detailBadges.append(span);
    }
  }

  function updateSearch() {
    const query = dom.search.value.trim().toLocaleLowerCase('en');
    allReaderNodes().removeClass('search-match');
    if (!query) {
      state.searchMatches = [];
      dom.searchStatus.textContent = '';
      return;
    }
    state.searchMatches = packet.nodes
      .filter((node) => [
        node.title, node.summary, node.intuition, node.importance, node.reasoning,
        node.formal.statement, node.formal.proof, node.formal.original_text
      ].join('\n').toLocaleLowerCase('en').includes(query))
      .map((node) => node.id);
    for (const id of state.searchMatches) cy.getElementById(id).addClass('search-match');
    dom.searchStatus.textContent = state.searchMatches.length
      ? bi(`${state.searchMatches.length} 个匹配 · 回车打开`, `${state.searchMatches.length} match${state.searchMatches.length === 1 ? '' : 'es'} · Enter to open`)
      : bi('没有匹配', 'No matches');
  }

  function openSearchMatch(nodeId) {
    const node = nodeById.get(nodeId);
    if (!node) return;
    let layerChanged = false;
    if (node.layer === 'research') {
      state.includeResearch = true;
      dom.research.checked = true;
      layerChanged = true;
    }
    if (node.plane === 'learning') {
      state.includeLearning = true;
      dom.learning.checked = true;
      layerChanged = true;
    }
    if (node.plane === 'reader') {
      state.includeReader = true;
      dom.reader.checked = true;
      layerChanged = true;
    }
    if (layerChanged) refreshForLayerChange();
    const element = cy.getElementById(nodeId);
    if (element.length && !element.hasClass('hidden')) {
      showNodeDetail(nodeId);
      updateNavigation();
      cy.animate({center: {eles: element}, duration: 250});
    }
  }

  function relationLabel(category) {
    return {
      prerequisite: bi('前置知识', 'Prerequisite'), support: bi('推导或支持', 'Derivation / support'),
      repair: bi('修复或替代', 'Repair / replacement'), conflict: bi('反驳或冲突', 'Refutation / conflict')
    }[category] || category;
  }

  function truthLabel(status) {
    return {
      admitted_fact: bi('已准入事实', 'Admitted Fact'), historical_inactive: bi('历史或停用', 'Historical / inactive'),
      source_authority: bi('仅来源权威', 'Source authority only'), interpretation: bi('仅解释', 'Interpretation only'),
      audit_evidence: bi('仅审计证据', 'Audit evidence only'), exploration: bi('仅探索', 'Exploration only'),
      learning: bi('仅学习证据', 'Learning evidence only'), reader_note: bi('仅读者注', 'Reader note only')
    }[status] || status;
  }

  function visualStatusLabel(status) {
    return {
      current: bi('当前', 'Current'), research: bi('研究中', 'Research'),
      challenged: bi('受质疑', 'Challenged'), inactive: bi('停用', 'Inactive')
    }[status] || titleCase(status);
  }

  function titleCase(value) {
    return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  async function typeset(containers) {
    if (!window.MathJax || !window.MathJax.startup || !window.MathJax.startup.promise) return;
    try {
      await window.MathJax.startup.promise;
      if (window.MathJax.typesetClear) window.MathJax.typesetClear(containers);
      await window.MathJax.typesetPromise(containers);
    } catch (error) {
      console.warn('Math typesetting unavailable; exact TeX remains readable.', error);
    }
  }

  async function copyText(text, button) {
    const label = button.querySelector('[data-zh][data-en]') || button;
    const copyEpoch = String((Number(button.dataset.copyEpoch) || 0) + 1);
    button.dataset.copyEpoch = copyEpoch;
    let copied = false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        copied = true;
      }
    } catch (error) {
      copied = false;
    }
    if (!copied) {
      const area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.append(area);
      area.select();
      copied = document.execCommand('copy');
      area.remove();
    }
    label.textContent = copied ? bi('已复制', 'Copied') : bi('无法复制', 'Copy unavailable');
    window.setTimeout(() => {
      if (!button.isConnected || button.dataset.copyEpoch !== copyEpoch) return;
      const idleZh = button.dataset.copyIdleZh || label.dataset.zh || '复制';
      const idleEn = button.dataset.copyIdleEn || label.dataset.en || 'Copy';
      label.textContent = state.locale === 'zh' ? idleZh : idleEn;
    }, 1300);
  }
})();
