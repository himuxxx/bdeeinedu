<?php
// এরর রিপোর্টিং বন্ধ করা (যাতে JSON আউটপুট নষ্ট না হয়)
error_reporting(0);
ini_set('display_errors', 0);

// JSON রেসপন্স হেডার সেট করা
header('Content-Type: application/json; charset=utf-8');

// eiin প্যারামিটার চেক করা
if (!isset($_GET['eiin']) || empty($_GET['eiin'])) {
    http_response_code(400);
    echo json_encode([
        'status'  => false,
        'message' => 'eiin প্যারামিটার প্রয়োজন। উদাহরণ: ?eiin=104532'
    ]);
    exit;
}

$eiin = trim($_GET['eiin']);

// EIIN ভ্যালিডেশন (শুধু সংখ্যা অনুমোদিত)
if (!ctype_digit($eiin)) {
    http_response_code(400);
    echo json_encode([
        'status'  => false,
        'message' => 'eiin প্যারামিটার অবশ্যই একটি সংখ্যা হতে হবে।'
    ]);
    exit;
}

/**
 * ইমেজ URL পূর্ণ করার হেল্পার ফাংশন
 */
function buildImageUrl(string $oldPath, $empId): string
{
    if (empty($oldPath) || empty($empId)) {
        return $oldPath;
    }
    $parts    = explode('/', $oldPath);
    $fileName = end($parts);
    return "https://apps.emis.gov.bd:9701/api/public/hrm/file/view/{$empId}/{$fileName}/10";
}

/**
 * সাধারণ cURL রিকোয়েস্ট ফাংশন
 */
function apiRequest(string $url, string $method, array $headers, ?string $body = null): array
{
    $ch = curl_init();

    $opts = [
        CURLOPT_URL            => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_TIMEOUT        => 30,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_SSL_VERIFYHOST => false,
        CURLOPT_HTTPHEADER     => $headers,
    ];

    if (strtoupper($method) === 'PUT') {
        $opts[CURLOPT_CUSTOMREQUEST] = 'PUT';
        if ($body !== null) {
            $opts[CURLOPT_POSTFIELDS] = $body;
        }
    } elseif (strtoupper($method) === 'POST') {
        $opts[CURLOPT_POST] = true;
        if ($body !== null) {
            $opts[CURLOPT_POSTFIELDS] = $body;
        }
    } else {
        $opts[CURLOPT_HTTPGET] = true;
    }

    curl_setopt_array($ch, $opts);

    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curlErr  = curl_error($ch);
    
    // curl_close() ডেপ্রিকেটেড, তাই সরানো হলো (PHP 8.0+ এ দরকার নেই)

    return [
        'response' => $response,
        'httpCode' => $httpCode,
        'error'    => $curlErr,
    ];
}

/* ============================================================
   ১) হেড/প্রিন্সিপাল-ভাইস প্রিন্সিপাল লিস্ট (GET)
   ============================================================ */
$urlHead = "https://apps.emis.gov.bd:9701/api/public/hrm/emp-info/get-head-by-institute-id/0/{$eiin}/0";

$headHeaders = [
    'Host: apps.emis.gov.bd:9701',
    'Connection: keep-alive',
    'sec-ch-ua-platform: "Android"',
    'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
    'Accept: application/json, text/plain, */*',
    'sec-ch-ua: "Chromium";v="154", "Android WebView";v="154", "Not A(Brand";v="99"',
    'sec-ch-ua-mobile: ?1',
    'Origin: https://apps.emis.gov.bd',
    'X-Requested-With: com.xbrowser.play',
    'Sec-Fetch-Site: same-site',
    'Sec-Fetch-Mode: cors',
    'Sec-Fetch-Dest: empty',
    'Referer: https://apps.emis.gov.bd/',
    'Accept-Encoding: gzip, deflate, br',
    'Accept-Language: en-US,en;q=0.9',
];

$headResult = apiRequest($urlHead, 'GET', $headHeaders);

if ($headResult['response'] === false) {
    http_response_code(500);
    echo json_encode(['status' => false, 'message' => 'Head API cURL error: ' . $headResult['error']]);
    exit;
}

$headData = json_decode($headResult['response'], true);
if (json_last_error() !== JSON_ERROR_NONE) {
    http_response_code(500);
    echo json_encode(['status' => false, 'message' => 'Head API returned invalid JSON']);
    exit;
}

if (isset($headData['data']) && is_array($headData['data'])) {
    foreach ($headData['data'] as &$item) {
        if (!empty($item['image'])) {
            $empId = $item['id'] ?? $item['empRefId'] ?? null;
            $item['image'] = buildImageUrl($item['image'], $empId);
        }
    }
    unset($item);
}

/* ============================================================
   ২) সম্পূর্ণ এমপ্লয়ি লিস্ট (PUT)
   ============================================================ */
$urlList = "https://apps.emis.gov.bd:9701/api/public/hrm/emp-info/get-pageable-emp-list-by-institute";

$listHeaders = [
    'Host: apps.emis.gov.bd:9701',
    'Connection: keep-alive',
    'sec-ch-ua-platform: "Android"',
    'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
    'Accept: application/json, text/plain, */*',
    'sec-ch-ua: "Chromium";v="154", "Android WebView";v="154", "Not A(Brand";v="99"',
    'Content-Type: application/json',
    'sec-ch-ua-mobile: ?1',
    'Origin: https://apps.emis.gov.bd',
    'X-Requested-With: com.xbrowser.play',
    'Sec-Fetch-Site: same-site',
    'Sec-Fetch-Mode: cors',
    'Sec-Fetch-Dest: empty',
    'Referer: https://apps.emis.gov.bd/',
    'Accept-Encoding: gzip, deflate, br',
    'Accept-Language: en-US,en;q=0.9',
];

$listBody = json_encode([
    'listIntParam1' => [],
    'page'          => 0,
    'size'          => 1000,
    'searchValue'   => '',
    'intParam1'     => null,
    'intParam2'     => 1,
    'stringParam1'  => $eiin,
]);

$listResult = apiRequest($urlList, 'PUT', $listHeaders, $listBody);

if ($listResult['response'] === false) {
    http_response_code(500);
    echo json_encode(['status' => false, 'message' => 'List API cURL error: ' . $listResult['error']]);
    exit;
}

$listData = json_decode($listResult['response'], true);
if (json_last_error() !== JSON_ERROR_NONE) {
    http_response_code(500);
    echo json_encode(['status' => false, 'message' => 'List API returned invalid JSON']);
    exit;
}

if (isset($listData['data']['content']) && is_array($listData['data']['content'])) {
    foreach ($listData['data']['content'] as &$item) {
        if (!empty($item['image'])) {
            $empId = $item['id'] ?? $item['empRefId'] ?? null;
            $item['image'] = buildImageUrl($item['image'], $empId);
        }
    }
    unset($item);
}

/* ============================================================
   ৩) দুটো রেসপন্স একত্রে আউটপুট দেওয়া (http_response_code(200) সরানো হলো)
   ============================================================ */
echo json_encode([
    'status'        => true,
    'eiin'          => $eiin,
    'headInfo'      => $headData,
    'employeeList'  => $listData,
    'Api_Owner'     => '@SHAKIB2016',
    'Telegram'      => '@SHAKIB2016',
    'Developer'     => '@SHAKIB2016',
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
