# k6 summary

scenario: aoi_summary

- http_req_sending: avg=0.052, min=0.010, med=0.051, max=0.160, p(90)=0.079, p(95)=0.097, p(99)=0.147
- http_req_connecting: max=0.148, p(90)=0.000, p(95)=0.000, p(99)=0.147, avg=0.006, min=0.000, med=0.000
- http_req_duration{expected_response:true}: p(90)=208.183, p(95)=225.886, p(99)=235.989, avg=183.605, min=159.777, med=179.676, max=238.348
- http_req_blocked: min=0.002, med=0.011, max=0.197, p(90)=0.014, p(95)=0.015, p(99)=0.195, avg=0.017
- http_req_receiving: min=0.089, med=0.191, max=0.783, p(90)=0.282, p(95)=0.647, p(99)=0.752, avg=0.224
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- iterations: rate=5.104, count=53.000
- http_req_waiting: avg=183.329, min=159.624, med=178.814, max=238.098, p(90)=207.965, p(95)=225.655, p(99)=235.785
- http_req_failed: rate=0.000
- vus: min=2.000, max=2.000
- http_req_duration: max=238.348, p(90)=208.183, p(95)=225.886, p(99)=235.989, avg=183.605, min=159.777, med=179.676
