# k6 summary

scenario: aoi_summary

- http_req_receiving: p(95)=0.819, p(99)=0.894, avg=0.288, min=0.096, med=0.226, max=0.912, p(90)=0.518
- http_req_duration{expected_response:true}: max=224.699, p(90)=211.971, p(95)=219.047, p(99)=223.569, avg=192.817, min=171.938, med=190.417
- http_req_failed: rate=0.000
- http_req_duration: p(90)=211.971, p(95)=219.047, p(99)=223.569, avg=192.817, min=171.938, med=190.417, max=224.699
- http_req_waiting: p(95)=218.578, p(99)=223.294, avg=192.470, min=171.686, med=190.158, max=224.473, p(90)=211.056
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_connecting: p(95)=0.004, p(99)=0.059, avg=0.004, min=0.000, med=0.000, max=0.072, p(90)=0.000
- http_req_sending: med=0.054, max=0.079, p(90)=0.077, p(95)=0.078, p(99)=0.078, avg=0.059, min=0.028
- iterations: count=20.000, rate=2.538
- vus: max=1.000, min=1.000
- http_req_blocked: p(95)=0.106, p(99)=0.170, avg=0.024, min=0.004, med=0.011, max=0.186, p(90)=0.023
