# k6 summary

scenario: replay

- http_req_waiting: avg=48.859, min=19.272, med=48.687, max=84.696, p(90)=58.579, p(95)=60.818, p(99)=79.920
- iterations: rate=3.997, count=20.000
- http_req_failed: rate=0.000
- http_req_duration: avg=49.133, min=19.485, med=48.852, max=84.976, p(90)=59.807, p(95)=61.586, p(99)=80.298
- http_req_receiving: p(99)=1.585, avg=0.231, min=0.081, med=0.123, max=1.841, p(90)=0.260, p(95)=0.563
- http_req_connecting: med=0.000, max=0.074, p(90)=0.000, p(95)=0.004, p(99)=0.060, avg=0.004, min=0.000
- http_req_blocked: avg=0.016, min=0.003, med=0.011, max=0.105, p(90)=0.014, p(95)=0.019, p(99)=0.088
- http_req_duration{expected_response:true}: p(90)=59.807, p(95)=61.586, p(99)=80.298, avg=49.133, min=19.485, med=48.852, max=84.976
- vus: min=1.000, max=1.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_sending: med=0.044, max=0.055, p(90)=0.052, p(95)=0.054, p(99)=0.055, avg=0.044, min=0.015
