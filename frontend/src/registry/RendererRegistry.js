import DocumentReader from '../components/MiddlePanel/DocumentReader.vue'
import ChatView from '../components/MiddlePanel/ChatView.vue'
import EntitiesView from '../components/MiddlePanel/EntitiesView.vue'
import QuestionViewer from '../components/MiddlePanel/QuestionViewer.vue'
import KnowledgeGraph from '../components/KnowledgeGraph/index.vue'

const registry = {
  document: DocumentReader,
  chat: ChatView,
  entities: EntitiesView,
  questions: QuestionViewer,
  knowledge_graph: KnowledgeGraph,
}

export function getRenderer(contentType) {
  return registry[contentType] || null
}

export default registry
