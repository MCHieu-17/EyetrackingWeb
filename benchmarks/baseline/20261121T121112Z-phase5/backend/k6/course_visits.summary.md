# k6 summary

scenario: course_visits

- http_req_duration{expected_response:true}: med=42.039, max=96.837, p(90)=70.482, p(95)=75.055, p(99)=79.663, avg=43.907, min=15.587
- vus: min=5.000, max=5.000
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_connecting: med=0.000, max=0.096, p(90)=0.000, p(95)=0.000, p(99)=0.085, avg=0.002, min=0.000
- http_req_waiting: med=41.865, max=96.705, p(90)=70.244, p(95)=74.707, p(99)=79.560, avg=43.699, min=15.436
- http_req_duration: avg=43.907, min=15.587, med=42.039, max=96.837, p(90)=70.482, p(95)=75.055, p(99)=79.663
- http_req_receiving: p(90)=0.310, p(95)=0.398, p(99)=0.721, avg=0.173, min=0.049, med=0.130, max=0.837
- http_req_failed: rate=0.000
- http_req_sending: p(95)=0.055, p(99)=0.073, avg=0.034, min=0.005, med=0.038, max=0.082, p(90)=0.049
- http_req_blocked: med=0.010, max=0.129, p(90)=0.013, p(95)=0.015, p(99)=0.112, avg=0.012, min=0.002
- iterations: rate=20.380, count=205.000
