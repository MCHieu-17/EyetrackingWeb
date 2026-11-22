# k6 summary

scenario: aoi_summary

- http_req_blocked: p(99)=0.089, avg=0.013, min=0.003, med=0.011, max=0.112, p(90)=0.014, p(95)=0.016
- iterations: count=90.000, rate=8.861
- vus: min=2.000, max=2.000
- http_req_duration: min=9.994, med=22.258, max=46.168, p(90)=36.202, p(95)=38.071, p(99)=46.061, avg=24.677
- http_req_waiting: p(90)=36.046, p(95)=37.842, p(99)=45.885, avg=24.532, min=9.920, med=22.092, max=46.037
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.078, p(90)=0.000, p(95)=0.000, p(99)=0.061
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_sending: avg=0.057, min=0.012, med=0.054, max=0.184, p(90)=0.078, p(95)=0.101, p(99)=0.137
- http_req_failed: rate=0.000
- http_req_receiving: max=0.501, p(90)=0.125, p(95)=0.191, p(99)=0.312, avg=0.089, min=0.024, med=0.075
- http_req_duration{expected_response:true}: p(95)=38.071, p(99)=46.061, avg=24.677, min=9.994, med=22.258, max=46.168, p(90)=36.202
