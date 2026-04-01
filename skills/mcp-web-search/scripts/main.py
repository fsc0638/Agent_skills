import os
import sys
import json
import requests

def main():
    # 1. 讀取參數 (從 STDIN 讀取 JSON)
    try:
        input_data = sys.stdin.read()
        args = json.loads(input_data) if input_data else {}
    except Exception as e:
        args = {}

    query = args.get("query")
    target_url = args.get("target_url")
    search_depth = args.get("search_depth", "basic")
    max_results = int(args.get("max_results", 3))
    include_domains = args.get("include_domains", [])  # e.g. ["udn.com", "ltn.com.tw"]

    # 2. 取得 API Key
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        print(json.dumps({"status": "error", "message": "Missing TAVILY_API_KEY environment variable."}))
        return

    # 3. 執行搜尋或擷取
    url = "https://api.tavily.com/extract" if target_url else "https://api.tavily.com/search"

    payload = {"api_key": api_key}

    if target_url:
        payload.update({
            "urls": [target_url],
            "include_raw_content": True,
        })
    else:
        q = (query or "").strip()
        if not q:
            print(json.dumps({"status": "error", "message": "Missing query."}, ensure_ascii=False))
            return

        payload.update({
            "query": q,
            "search_depth": search_depth,
            "max_results": max_results,  # 用你一開始解析好的 max_results
            "include_raw_content": True if search_depth == "advanced" else False,
        })
        if include_domains:
            payload["include_domains"] = include_domains

    try:
        response = requests.post(url, json=payload, timeout=30)
        try:
            response.raise_for_status()
        except Exception:
            # Return Tavily error body for debugging (never echo api_key)
            try:
                err_text = response.text
            except Exception:
                err_text = ""
            safe_payload = {k: v for k, v in payload.items() if k != "api_key"}
            print(json.dumps({
                "status": "error",
                "message": f"API 執行失敗: {response.status_code} {response.reason}",
                "url": url,
                "sent_payload": safe_payload,
                "tavily_body": (err_text or "")[:2000],
            }, ensure_ascii=False))
            return

        data = response.json()
        
        # 處理 Extract 模式 (target_url)
        if target_url:
            results = data.get("results", [])
            if not results:
                print(json.dumps({"status": "error", "message": f"無法從網址讀取內容：{target_url}"}))
                return
            
            res = results[0]
            content = res.get("raw_content") or res.get("content") or ""
            # Token 保護：截斷至 3000 字元
            truncated = content[:3000] + "..." if len(content) > 3000 else content
            print(json.dumps({
                "status": "success",
                "mode": "extract",
                "data": {
                    "title": res.get("title"),
                    "url": res.get("url"),
                    "content": truncated
                }
            }, ensure_ascii=False))
            return

        # 處理 Search 模式 (query)
        results = data.get("results", [])
        if not results:
            print(json.dumps({"status": "success", "message": f"找不到關於『{query}』的搜尋結果。", "results": []}))
            return

        output_results = []
        for res in results:
            content = res.get("raw_content") or res.get("content") or ""
            # Token 保護：每個網頁最多 2000 字元
            truncated_content = content[:2000] + "..." if len(content) > 2000 else content
            output_results.append({
                "title": res.get("title"),
                "url": res.get("url"),
                "content": truncated_content
            })
            
        print(json.dumps({"status": "success", "mode": "search", "results": output_results}, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"status": "error", "message": f"API 執行失敗: {str(e)}"}))

if __name__ == "__main__":
    main()
