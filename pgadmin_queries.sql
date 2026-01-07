-- ============================================
-- PostgreSQL Memory Tables - Useful Queries
-- ============================================
-- Copy and paste these queries in pgAdmin Query Tool
-- ============================================

-- 1. List all conversation memory tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name LIKE 'conversation%'
ORDER BY table_name;

-- 2. View all conversation threads (metadata)
SELECT 
    thread_id,
    cooperative,
    user_id,
    session_id,
    message_count,
    last_message_at,
    current_topic,
    created_at,
    updated_at
FROM conversation_threads
ORDER BY updated_at DESC;

-- 3. View all conversation messages (full history)
SELECT 
    id,
    thread_id,
    message_role,
    message_content,
    message_order,
    tools_used,
    metadata,
    created_at
FROM conversation_messages
ORDER BY thread_id, message_order;

-- 4. View messages for a specific thread
SELECT 
    message_order,
    message_role,
    message_content,
    tools_used,
    created_at
FROM conversation_messages
WHERE thread_id = 'chat_Leads_11_session-xxxxx'  -- Replace with your thread_id
ORDER BY message_order;

-- 5. Count messages per thread
SELECT 
    thread_id,
    COUNT(*) as message_count,
    MAX(created_at) as last_message
FROM conversation_messages
GROUP BY thread_id
ORDER BY last_message DESC;

-- 6. View conversation summary (if exists)
SELECT 
    thread_id,
    summary_text,
    summarized_messages_count,
    summarized_at
FROM conversation_summaries
ORDER BY summarized_at DESC;

-- 7. Get latest conversation for a specific cooperative and user
SELECT 
    t.thread_id,
    t.cooperative,
    t.user_id,
    t.message_count,
    t.last_message_at,
    COUNT(m.id) as actual_message_count
FROM conversation_threads t
LEFT JOIN conversation_messages m ON t.thread_id = m.thread_id
WHERE t.cooperative = 'Leads'  -- Replace with your cooperative
  AND t.user_id = '11'         -- Replace with your user_id
GROUP BY t.thread_id, t.cooperative, t.user_id, t.message_count, t.last_message_at
ORDER BY t.last_message_at DESC
LIMIT 1;

-- 8. View full conversation with thread info
SELECT 
    t.thread_id,
    t.cooperative,
    t.user_id,
    m.message_order,
    m.message_role,
    m.message_content,
    m.tools_used,
    m.created_at
FROM conversation_threads t
JOIN conversation_messages m ON t.thread_id = m.thread_id
WHERE t.thread_id = 'chat_Leads_11_session-xxxxx'  -- Replace with your thread_id
ORDER BY m.message_order;

-- 9. Check table structure (columns)
SELECT 
    column_name,
    data_type,
    character_maximum_length,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public' 
AND table_name = 'conversation_threads'  -- Change to conversation_messages or conversation_summaries
ORDER BY ordinal_position;

-- 10. Get statistics
SELECT 
    (SELECT COUNT(*) FROM conversation_threads) as total_threads,
    (SELECT COUNT(*) FROM conversation_messages) as total_messages,
    (SELECT COUNT(*) FROM conversation_summaries) as total_summaries,
    (SELECT COUNT(DISTINCT thread_id) FROM conversation_messages) as threads_with_messages;

