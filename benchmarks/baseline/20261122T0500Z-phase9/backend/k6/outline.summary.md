# k6 summary

scenario: outline

- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_blocked: max=0.124, p(90)=0.013, p(95)=0.017, p(99)=0.121, avg=0.013, min=0.002, med=0.011
- iterations: count=240.000, rate=23.529
- vus: min=5.000, max=5.000
- http_req_duration{expected_response:true}: max=49.894, p(90)=13.528, p(95)=13.802, p(99)=33.921, avg=9.399, min=1.983, med=8.953
- http_req_receiving: max=0.892, p(90)=0.277, p(95)=0.372, p(99)=0.824, avg=0.159, min=0.016, med=0.143
- http_req_connecting: p(95)=0.000, p(99)=0.086, avg=0.002, min=0.000, med=0.000, max=0.089, p(90)=0.000
- http_req_sending: p(95)=0.061, p(99)=0.080, avg=0.039, min=0.009, med=0.039, max=0.123, p(90)=0.050
- http_req_waiting: p(99)=33.799, avg=9.201, min=1.920, med=8.717, max=49.822, p(90)=13.250, p(95)=13.589
- http_req_duration: avg=9.399, min=1.983, med=8.953, max=49.894, p(90)=13.528, p(95)=13.802, p(99)=33.921
- http_req_failed: rate=0.000
