import os
import requests
import json

def execute_tavily_search(query=None, target_url=None, search_depth="basic", max_results=3):
    """
    Tavily Search API 執行器
    支援全網搜尋 (query) 或指定網址內容擷取 (target_url)
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return "錯誤：找不到 TAVILY_API_KEY，請在 .env 中設定。"

    # API Endpoint 決定
    # 如果有 target_url，使用 extract 端點；否則使用 search 端點
    url = "https://api.tavily.com/extract" if target_url else "https://api.tavily.com/search"
    
    payload = {
        "api_key": api_key,
    }

    if target_url:
        payload["urls"] = [target_url]
    else:
        payload.update({
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_raw_content": True if search_depth == "advanced" else False
        })

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # 處理 Extract 模式 (target_url)
        if target_url:
            results = data.get("results", [])
            if not results:
                return f"無法從網址讀取內容：{target_url}"
            
            res = results[0]
            content = res.get("raw_content") or res.get("content") or ""
            # Token 保護：截斷至 3000 字元 (Extract 模式給稍微寬一點)
            truncated = content[:3000] + "..." if len(content) > 3000 else content
            return f"Title: {res.get('title')}\nURL: {res.get('url')}\nContent: {truncated}"

        # 處理 Search 模式 (query)
        results = data.get("results", [])
        if not results:
            return f"找不到關於『{query}』的搜尋結果。"

        formatted_output = ""
        for idx, res in enumerate(results):
            content = res.get("raw_content") or res.get("content") or ""
            # Token 保護：防爆機制 (每個網頁最多 2000 字元)
            truncated_content = content[:2000] + "..." if len(content) > 2000 else content
            formatted_output += f"[{idx+1}] Title: {res.get('title')}\nURL: {res.get('url')}\nContent: {truncated_content}\n\n"
            
        return formatted_output

    except Exception as e:
        return f"搜尋執行失敗：{str(e)}"

# 範例執行 (僅供參考)
# print(execute_tavily_search(query="2024 AI 發展"))
# print(execute_tavily_search(target_url="https://example.com"))
