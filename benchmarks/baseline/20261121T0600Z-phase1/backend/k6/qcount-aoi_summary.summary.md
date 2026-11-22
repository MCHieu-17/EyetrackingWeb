# k6 summary

scenario: aoi_summary

- iterations: count=20.000, rate=2.620
- http_req_duration: max=223.260, p(90)=195.355, p(95)=205.773, p(99)=219.762, avg=180.558, min=158.295, med=183.099
- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.074, p(90)=0.000, p(95)=0.004, p(99)=0.060
- http_req_sending: max=0.094, p(90)=0.076, p(95)=0.077, p(99)=0.091, avg=0.056, min=0.015, med=0.054
- http_req_receiving: p(95)=0.513, p(99)=0.595, avg=0.249, min=0.082, med=0.203, max=0.615, p(90)=0.446
- http_req_failed: rate=0.000
- http_req_blocked: min=0.003, med=0.011, max=0.105, p(90)=0.017, p(95)=0.029, p(99)=0.090, avg=0.016
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_waiting: p(95)=205.601, p(99)=219.385, avg=180.253, min=158.079, med=182.786, max=222.831, p(90)=195.079
- vus: min=1.000, max=1.000
- http_req_duration{expected_response:true}: med=183.099, max=223.260, p(90)=195.355, p(95)=205.773, p(99)=219.762, avg=180.558, min=158.295
