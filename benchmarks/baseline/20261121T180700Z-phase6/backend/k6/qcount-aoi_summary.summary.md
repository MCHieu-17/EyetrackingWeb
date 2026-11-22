# k6 summary

scenario: aoi_summary

- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_duration{expected_response:true}: med=179.180, max=215.128, p(90)=204.277, p(95)=211.448, p(99)=214.392, avg=184.707, min=168.019
- http_req_failed: rate=0.000
- vus: min=1.000, max=1.000
- http_req_duration: med=179.180, max=215.128, p(90)=204.277, p(95)=211.448, p(99)=214.392, avg=184.707, min=168.019
- http_req_sending: avg=0.061, min=0.016, med=0.059, max=0.118, p(90)=0.072, p(95)=0.093, p(99)=0.113
- http_req_waiting: p(90)=204.026, p(95)=211.084, p(99)=214.104, avg=184.360, min=167.765, med=178.912, max=214.859
- http_req_blocked: p(95)=0.030, p(99)=0.096, avg=0.017, min=0.004, med=0.011, max=0.112, p(90)=0.014
- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.079, p(90)=0.000, p(95)=0.004, p(99)=0.064
- iterations: count=20.000, rate=2.592
- http_req_receiving: p(99)=0.771, avg=0.287, min=0.122, med=0.229, max=0.805, p(90)=0.424, p(95)=0.635
